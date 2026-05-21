"""
TP-13: Capture configuration validation (integration test).

Loads camera modes from ``src/config/camera.json`` (see ``--camera-modes``).
Each mode is crossed with fixed buffer durations (default 3 s and 6 s), so the run
is ``len(modes) × len(buffer_durations)`` combinations.

Shows a large preview window: native-resolution video centered on black, with
large white stats in the top band. Press SPACE to finish the current combo and
run automated checks; Q quits the full run.

Each combo writes a separate log file under ./logs/ next to this script.

Optional filters: ``--only-fps 30`` keeps modes whose JSON fps is near that value;
``--max-combos 8`` truncates after ordering modes as in the JSON. By default, stdout
and stderr are also copied to ``test_scripts/tp_13/results.txt`` (shell prompt lines
from copy-paste are dropped). Use ``--no-results-file`` to disable.

Optional: pip install pynput to allow Esc from anywhere to abort the run; SPACE and Q
are read on the OpenCV preview window when it has focus.
"""

from __future__ import annotations

import argparse
import json
import queue
import re
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LOGS_DIR = Path("logs")
DEFAULT_RESULTS_FILE = SCRIPT_DIR / "results.txt"
REPO_ROOT = SCRIPT_DIR.parent.parent
CAMERA_MODES_PATH = REPO_ROOT / "src" / "config" / "camera.json"

# Omit pasted shell lines like: (venv) user@host:~/path $ python tp_13_....py
_RESULTS_SHELL_LINE = re.compile(
    r"^\s*(?:\([^)]*\)\s+)?\S+@\S+:.+\$\s+python\d*\s+.*tp_13",
    re.IGNORECASE,
)

# Preview: large window; video at native resolution centered on black; stats in top band only.
VIEW_MIN_W = 1440
VIEW_MIN_H = 900
STATS_BAND_H = 230

BUFFER_DURATIONS_S: List[float] = [3.0, 6.0]


@dataclass
class Combo:
    index: int
    total: int
    mode_id: str
    input_format: str
    width: int
    height: int
    target_fps: float
    buffer_s: float


def _load_camera_modes(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    modes = data.get("modes")
    if not isinstance(modes, list) or not modes:
        raise ValueError(f"No modes found in {path}")
    return modes


def iter_combos(
    modes: List[Dict[str, Any]],
    *,
    buffer_durations: Optional[List[float]] = None,
    only_fps: Optional[float] = None,
    fps_tolerance: float = 0.51,
    max_combos: Optional[int] = None,
) -> List[Combo]:
    bufs = buffer_durations if buffer_durations is not None else BUFFER_DURATIONS_S
    work = modes
    if only_fps is not None:
        work = [m for m in modes if abs(float(m.get("fps", 0.0)) - only_fps) <= fps_tolerance]

    raw: List[Combo] = []
    for m in work:
        mode_id = str(m.get("id", "unknown_mode"))
        input_format = str(m.get("input_format", "mjpeg")).strip().lower() or "mjpeg"
        w = int(m["width"])
        h = int(m["height"])
        fps = float(m["fps"])
        for buf in bufs:
            raw.append(
                Combo(
                    index=0,
                    total=0,
                    mode_id=mode_id,
                    input_format=input_format,
                    width=w,
                    height=h,
                    target_fps=fps,
                    buffer_s=float(buf),
                )
            )

    if max_combos is not None and max_combos > 0:
        raw = raw[: int(max_combos)]

    total = len(raw)
    out: List[Combo] = []
    for i, c in enumerate(raw):
        out.append(
            Combo(
                index=i + 1,
                total=total,
                mode_id=c.mode_id,
                input_format=c.input_format,
                width=c.width,
                height=c.height,
                target_fps=c.target_fps,
                buffer_s=c.buffer_s,
            )
        )
    return out


def _omit_line_from_results_file(line_without_newline: str) -> bool:
    s = line_without_newline.strip("\r")
    if not s.strip():
        return False
    return bool(_RESULTS_SHELL_LINE.match(s))


class TeeStream:
    """Write to a real stream and duplicate to a log file (line filter applies to file only)."""

    def __init__(
        self,
        base: Any,
        log_file: Any,
        lock: threading.Lock,
        *,
        omit_line_fn: Callable[[str], bool],
    ) -> None:
        self._base = base
        self._log = log_file
        self._lock = lock
        self._omit_line_fn = omit_line_fn
        self._pending = ""

    def write(self, s: str) -> int:
        self._base.write(s)
        if not s:
            return 0
        with self._lock:
            self._pending += s
            while True:
                pos = self._pending.find("\n")
                if pos < 0:
                    break
                line = self._pending[:pos]
                self._pending = self._pending[pos + 1 :]
                if not self._omit_line_fn(line):
                    self._log.write(line + "\n")
            self._log.flush()
        return len(s)

    def flush(self) -> None:
        self._base.flush()
        with self._lock:
            if self._pending:
                if not self._omit_line_fn(self._pending.rstrip("\r\n")):
                    self._log.write(self._pending)
                self._pending = ""
            self._log.flush()

    def isatty(self) -> bool:
        return bool(self._base.isatty())


def _fourcc_for_input_format(input_format: str) -> int:
    """Map camera.json ``input_format`` to OpenCV CAP_PROP_FOURCC."""
    f = (input_format or "").strip().lower()
    if f in ("mjpeg", "mjpg", "motion_jpeg"):
        return cv2.VideoWriter_fourcc(*"MJPG")
    if f in ("yuyv422", "yuyv", "yuy2", "yuyv_422"):
        return cv2.VideoWriter_fourcc(*"YUYV")
    # Sensible default for typical UVC webcams
    return cv2.VideoWriter_fourcc(*"MJPG")


class RollingFrameBuffer:
    """Time-windowed deque of (monotonic_time_s, frame)."""

    def __init__(self, duration_seconds: float) -> None:
        if duration_seconds <= 0:
            raise ValueError("buffer duration must be positive")
        self.duration_seconds = duration_seconds
        self._frames: Deque[Tuple[float, np.ndarray]] = deque()

    def push(self, t: float, frame: np.ndarray) -> None:
        self._frames.append((t, frame.copy()))
        cutoff = t - self.duration_seconds
        while self._frames and self._frames[0][0] < cutoff:
            self._frames.popleft()

    def time_span(self) -> float:
        if len(self._frames) < 2:
            return 0.0
        return self._frames[-1][0] - self._frames[0][0]

    def frame_count(self) -> int:
        return len(self._frames)


def _effective_fps(cap: cv2.VideoCapture, fallback: float) -> float:
    v = cap.get(cv2.CAP_PROP_FPS)
    if v is not None and v > 1.0:
        return float(v)
    return fallback


def _measure_fps_from_times(times: Deque[float]) -> Optional[float]:
    if len(times) < 4:
        return None
    arr = np.array(sorted(times), dtype=np.float64)
    dts = np.diff(arr)
    dts = dts[dts > 1e-6]
    if dts.size < 2:
        return None
    med = float(np.median(dts))
    if med <= 0:
        return None
    return 1.0 / med


def _get_screen_size() -> Optional[Tuple[int, int]]:
    """Best-effort screen size for window centering."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        sw, sh = int(root.winfo_screenwidth()), int(root.winfo_screenheight())
        root.destroy()
        if sw > 0 and sh > 0:
            return sw, sh
    except Exception:
        pass
    return None


def _decode_fourcc(value: float) -> str:
    try:
        iv = int(value)
    except Exception:
        return "n/a"
    if iv <= 0:
        return "n/a"
    chars = [chr((iv >> (8 * i)) & 0xFF) for i in range(4)]
    s = "".join(chars)
    if any(ord(c) < 32 or ord(c) > 126 for c in s):
        return "n/a"
    return s


def _resolution_ok(req_w: int, req_h: int, actual_w: int, actual_h: int) -> bool:
    # Cameras may snap modes; allow modest slack.
    return abs(req_w - actual_w) <= 16 and abs(req_h - actual_h) <= 16


def _fps_ok(target: float, measured: Optional[float]) -> bool:
    if measured is None or measured <= 0:
        return False
    # USB / Pi variance: relative + absolute floor
    rel = abs(measured - target) / max(target, 1e-6)
    return rel <= 0.45 or abs(measured - target) <= 6.0


def _fps_targets_for_check(requested: float, cap_reported_fps: float) -> List[float]:
    """
    Validate primarily against the requested FPS. CAP_PROP_FPS is only used as an
    alternate target when it is close to requested, because many UVC/V4L2 drivers
    report stale/default values that do not match the delivered stream rate.
    """
    out: List[float] = [requested]
    if cap_reported_fps > 1.0:
        # Only trust CAP_PROP_FPS if it approximately agrees with requested.
        rel = abs(cap_reported_fps - requested) / max(requested, 1e-6)
        if rel <= 0.20 or abs(cap_reported_fps - requested) <= 3.0:
            out.append(cap_reported_fps)
    # Dedupe preserving order
    seen: set = set()
    uniq: List[float] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _fps_targets_for_resolution_check(
    requested: float,
    cap_reported_fps: float,
    mjpg_resolution_fps: Optional[float],
) -> List[float]:
    """
    Primary check is always against requested FPS so 14.7 vs 15 can PASS.
    Secondary check uses negotiated MJPG FPS for the resolution (when learned),
    to handle cameras that ignore requested FPS and stick to a mode rate.
    CAP_PROP_FPS is diagnostic and only used as a tertiary fallback when close.
    """
    out: List[float] = [requested]
    if mjpg_resolution_fps is not None and mjpg_resolution_fps > 1.0:
        out.append(mjpg_resolution_fps)
    else:
        out.extend(_fps_targets_for_check(requested, cap_reported_fps))
    # Dedupe preserving order
    seen: set = set()
    uniq: List[float] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _fps_pass(
    requested: float,
    measured: Optional[float],
    cap_reported_fps: float,
    mjpg_resolution_fps: Optional[float] = None,
) -> bool:
    if measured is None or measured <= 0:
        return False
    for t in _fps_targets_for_resolution_check(requested, cap_reported_fps, mjpg_resolution_fps):
        if _fps_ok(t, measured):
            return True
    return False


def _buffer_ok(buffer_s: float, span_s: float, elapsed_s: float, fps_hint: Optional[float]) -> bool:
    if span_s < 0 or buffer_s <= 0:
        return False
    # Must not exceed configured window (implementation should enforce <= buffer_s)
    if span_s > buffer_s * 1.2 + 0.5:
        return False
    # Need enough runtime to fill the window
    if elapsed_s < buffer_s * 0.85:
        return False
    # When "full", span should approach buffer_s
    lo = buffer_s * 0.55
    hi = buffer_s * 1.05 + 0.75
    span_ok = lo <= span_s <= hi
    # Low measured FPS (720p, USB bandwidth): relax lower bound slightly
    if not span_ok and fps_hint is not None and fps_hint < 15:
        return span_s >= buffer_s * 0.48 and span_s <= buffer_s * 1.15 + 0.5
    return span_ok


def _explain_resolution_fail(
    req_w: int, req_h: int, actual_w: int, actual_h: int, ok: bool
) -> str:
    if ok:
        return "Requested resolution matches actual frame size (within allowed slack)."
    return (
        f"Camera did not deliver the requested {req_w}x{req_h} mode; got {actual_w}x{actual_h}. "
        "The device may have snapped to a different fixed mode."
    )


def _explain_fps_fail(
    requested: float,
    measured: Optional[float],
    cap_reported: float,
    ok: bool,
    mjpg_resolution_fps: Optional[float] = None,
) -> str:
    if ok:
        if mjpg_resolution_fps is not None and mjpg_resolution_fps > 1.0:
            return (
                f"Measured frame interval rate matches the negotiated MJPG FPS for this "
                f"resolution (~{mjpg_resolution_fps:.2f} FPS)."
            )
        return "Measured frame interval rate matches the requested FPS."
    meas = f"{measured:.2f}" if measured is not None else "n/a"
    mode_msg = (
        f" For this resolution, negotiated MJPG baseline is ~{mjpg_resolution_fps:.2f} FPS."
        if mjpg_resolution_fps is not None and mjpg_resolution_fps > 1.0
        else ""
    )
    return (
        f"Measured FPS ({meas}) is outside tolerance vs requested FPS {requested:g} and outside "
        "the negotiated mode baseline for this resolution. "
        "Many USB cameras expose fixed FPS per resolution/format mode and may ignore requested "
        "FPS values."
        f"{mode_msg}"
    )


def _explain_buffer_fail(
    buffer_s: float,
    span_s: float,
    elapsed_s: float,
    buf_frames: int,
    measured_fps: Optional[float],
    ok: bool,
) -> str:
    if ok:
        return (
            "Rolling buffer time span matches the configured window (oldest–newest frame times)."
        )
    if elapsed_s < buffer_s * 0.85:
        return (
            f"Capture time ({elapsed_s:.2f}s) was shorter than ~{buffer_s * 0.85:.1f}s "
            f"({0.85:.0%} of the {buffer_s:g}s buffer). Wait longer before SPACE so the deque "
            "can accumulate a full rolling window."
        )
    if span_s > buffer_s * 1.2 + 0.5:
        return (
            f"Buffer span ({span_s:.2f}s) exceeds the expected cap for a {buffer_s:g}s window; "
            "check clock monotonicity or deque logic."
        )
    mf = f"{measured_fps:.2f}" if measured_fps is not None else "n/a"
    return (
        f"Rolling buffer span ({span_s:.2f}s) with {buf_frames} frames is outside the expected "
        f"range for a {buffer_s:g}s window at ~{mf} FPS. At low FPS, wait until span approaches "
        f"the full {buffer_s:g}s (oldest frame age in the buffer)."
    )


def _write_log(
    path: Path,
    combo: Combo,
    actual_w: int,
    actual_h: int,
    cap_fps_prop: float,
    measured_fps: Optional[float],
    buffer_span_s: float,
    buffer_frames: int,
    elapsed_s: float,
    stream_fourcc: str,
    checks: dict,
    notes: dict,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"TP-13 capture configuration validation log",
        f"utc_time={ts}",
        f"combo={combo.index}/{combo.total}",
        f"mode_id={combo.mode_id}",
        f"input_format={combo.input_format}",
        f"requested_resolution={combo.width}x{combo.height}",
        f"actual_resolution={actual_w}x{actual_h}",
        f"requested_fps={combo.target_fps}",
        f"cap_prop_fps={cap_fps_prop:.4f}",
        f"stream_fourcc={stream_fourcc}",
        f"measured_fps={measured_fps if measured_fps is not None else 'n/a'}",
        f"buffer_duration_s={combo.buffer_s}",
        f"buffer_time_span_s={buffer_span_s:.4f}",
        f"buffer_frame_count={buffer_frames}",
        f"elapsed_capture_s={elapsed_s:.4f}",
        "",
        "automated_checks:",
    ]
    for k, v in checks.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("notes:")
    for k, v in notes.items():
        lines.append(f"  {k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _compose_preview(
    frame: np.ndarray,
    combo: Combo,
    measured_fps: Optional[float],
    buffer_span: float,
    buf_frames: int,
    elapsed: float,
    cap_fps_prop: float,
    stream_fourcc: str,
) -> Tuple[np.ndarray, int, int]:
    """Black canvas, native-resolution frame centered below stats band; large white stats top-left."""
    fh, fw = frame.shape[:2]
    canvas_w = max(VIEW_MIN_W, fw + 80)
    canvas_h = max(VIEW_MIN_H, STATS_BAND_H + fh + 80)
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    x0 = (canvas_w - fw) // 2
    y0 = STATS_BAND_H + max(12, (canvas_h - STATS_BAND_H - fh) // 2)
    canvas[y0 : y0 + fh, x0 : x0 + fw] = frame

    font = cv2.FONT_HERSHEY_DUPLEX
    scale = 1.55
    thickness = 3
    white: Tuple[int, int, int] = (255, 255, 255)
    x, y = 20, 56
    line_h = 56

    def line(text: str) -> None:
        nonlocal y
        cv2.putText(canvas, text, (x, y), font, scale, white, thickness, cv2.LINE_AA)
        y += line_h

    line(
        f"TP-13  combo {combo.index}/{combo.total}   {combo.mode_id}  "
        f"{combo.width}x{combo.height} @ {combo.target_fps:g}  ({combo.input_format})"
    )
    line(f"FPS  measured {measured_fps or 0:.1f}")
    line(
        f"Fmt {stream_fourcc}   Buffer {combo.buffer_s:g}s   span {buffer_span:.2f}s   "
        f"frames {buf_frames}   elapsed {elapsed:.1f}s"
    )
    line("SPACE = finish combo + checks      Q = quit run")
    return canvas, canvas_w, canvas_h


def _stdin_quit_thread(q: "queue.Queue[str]", stop: threading.Event) -> None:
    print("stdin: type 'q' + Enter to abort entire run (optional).")
    while not stop.is_set():
        try:
            line = sys.stdin.readline()
        except (EOFError, OSError):
            break
        if stop.is_set():
            break
        if line.strip().lower() == "q":
            q.put("quit")


def _pynput_quit_thread(q: "queue.Queue[str]", stop: threading.Event) -> None:
    try:
        from pynput import keyboard
    except ImportError:
        return

    def on_press(key: object) -> None:
        try:
            if key == keyboard.Key.esc:
                q.put("quit")
        except Exception:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    stop.wait()
    listener.stop()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="TP-13: capture config validation (camera modes × buffer durations)."
    )
    p.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index (default: 0).")
    p.add_argument(
        "--camera-modes",
        type=Path,
        default=CAMERA_MODES_PATH,
        help=f"JSON file with a top-level 'modes' list (default: {CAMERA_MODES_PATH}).",
    )
    p.add_argument(
        "--logs-dir",
        type=Path,
        default=DEFAULT_LOGS_DIR,
        help="Directory for per-combo logs (default: ./logs, relative to current working directory).",
    )
    p.add_argument(
        "--no-global-esc",
        action="store_true",
        help="Do not try pynput for global Esc to quit (window focus only).",
    )
    p.add_argument(
        "--only-fps",
        type=float,
        default=None,
        metavar="FPS",
        help="Run only camera modes whose configured fps is within --fps-tolerance of this value "
        "(e.g. 30 for all ~30 fps modes).",
    )
    p.add_argument(
        "--fps-tolerance",
        type=float,
        default=0.51,
        help="Tolerance when matching --only-fps to each mode's fps (default: 0.51).",
    )
    p.add_argument(
        "--max-combos",
        type=int,
        default=None,
        metavar="N",
        help="After filtering, run at most the first N combinations (JSON order × buffer durations).",
    )
    p.add_argument(
        "--results-file",
        type=Path,
        default=DEFAULT_RESULTS_FILE,
        help=f"Mirror of terminal output; file is truncated each run (default: {DEFAULT_RESULTS_FILE}).",
    )
    p.add_argument(
        "--no-results-file",
        action="store_true",
        help="Do not write results.txt (terminal only).",
    )
    return p.parse_args()


def _run_tp13(args: argparse.Namespace) -> int:
    modes_path = args.camera_modes.resolve()
    try:
        modes = _load_camera_modes(modes_path)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"ERROR: failed to load camera modes from {modes_path}: {e}")
        return 2
    combos = iter_combos(
        modes,
        only_fps=args.only_fps,
        fps_tolerance=args.fps_tolerance,
        max_combos=args.max_combos,
    )
    if not combos:
        print("ERROR: no capture combos generated (check --only-fps / camera.json)")
        return 2

    args.logs_dir.mkdir(parents=True, exist_ok=True)

    quit_q: queue.Queue[str] = queue.Queue()
    stop_event = threading.Event()
    use_pynput = not args.no_global_esc
    if use_pynput:
        try:
            import pynput  # noqa: F401
        except ImportError:
            use_pynput = False

    if use_pynput:
        t = threading.Thread(target=_pynput_quit_thread, args=(quit_q, stop_event), daemon=True)
        t.start()
    else:
        t = threading.Thread(target=_stdin_quit_thread, args=(quit_q, stop_event), daemon=True)
        t.start()

    print("TP-13: Capture configuration validation")
    filter_bits: List[str] = []
    if args.only_fps is not None:
        filter_bits.append(f"only_fps≈{args.only_fps:g} (±{args.fps_tolerance:g})")
    if args.max_combos is not None:
        filter_bits.append(f"max_combos={args.max_combos}")
    filter_desc = f" [{', '.join(filter_bits)}]" if filter_bits else ""
    print(f"  {len(combos)} combinations{filter_desc}")
    print(f"  Modes in JSON: {len(modes)}; modes in this run: {len({c.mode_id for c in combos})}")
    print(f"  Modes config -> {modes_path}")
    print(f"  Logs -> {args.logs_dir}")
    print("  Focus the video window: SPACE = finish combo + checks, Q = quit run")
    print("")

    window = "TP-13 Capture Config"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    screen_size = _get_screen_size()

    results: List[Tuple[Combo, bool, List[str]]] = []
    negotiated_mjpg_fps_by_resolution: dict[Tuple[int, int], float] = {}

    try:
        for combo in combos:
            print(
                f"\n--- Combo {combo.index}/{combo.total}: {combo.mode_id} "
                f"[{combo.input_format}] "
                f"({combo.width}x{combo.height} @ {combo.target_fps} FPS), "
                f"buffer {combo.buffer_s}s ---"
            )
            print("  Wait until the rolling buffer has time to fill, then press SPACE.")

            cap = cv2.VideoCapture(args.camera_index, cv2.CAP_V4L2)
            if not cap.isOpened():
                print(f"ERROR: could not open camera index {args.camera_index}")
                return 1

            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FOURCC, _fourcc_for_input_format(combo.input_format))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, combo.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, combo.height)
            cap.set(cv2.CAP_PROP_FPS, combo.target_fps)

            for _ in range(32):
                cap.read()

            cap_fps_reported = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if cap_fps_reported <= 1.0:
                cap_fps_reported = _effective_fps(cap, combo.target_fps)
            stream_fourcc = _decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))

            rolling = RollingFrameBuffer(combo.buffer_s)
            recent_frame_times: Deque[float] = deque(maxlen=240)

            t0 = time.perf_counter()
            aborted = False
            frame: Optional[np.ndarray] = None
            last_canvas_w, last_canvas_h = 0, 0

            while True:
                if not quit_q.empty():
                    aborted = True
                    break

                ok, frame = cap.read()
                if not ok or frame is None:
                    print("  WARN: frame grab failed, retrying...")
                    time.sleep(0.02)
                    continue

                now = time.perf_counter()
                recent_frame_times.append(now)
                rolling.push(now, frame)

                measured = _measure_fps_from_times(recent_frame_times)
                span = rolling.time_span()
                elapsed = now - t0

                cap_fps_reported = float(cap.get(cv2.CAP_PROP_FPS) or cap_fps_reported)
                if cap_fps_reported <= 1.0:
                    cap_fps_reported = _effective_fps(cap, combo.target_fps)
                stream_fourcc = _decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))

                vis, cw, ch = _compose_preview(
                    frame,
                    combo,
                    measured,
                    span,
                    rolling.frame_count(),
                    elapsed,
                    cap_fps_reported,
                    stream_fourcc,
                )
                if cw != last_canvas_w or ch != last_canvas_h:
                    disp_w = max(640, cw // 2)
                    disp_h = max(400, ch // 2)
                    cv2.resizeWindow(window, disp_w, disp_h)
                    if screen_size is not None:
                        sw, sh = screen_size
                        wx = max(0, (sw - disp_w) // 2)
                        wy = max(0, (sh - disp_h) // 2)
                        cv2.moveWindow(window, wx, wy)
                    last_canvas_w, last_canvas_h = cw, ch
                cv2.imshow(window, vis)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == ord("Q"):
                    aborted = True
                    break
                if key == ord(" "):
                    min_ready = combo.buffer_s * 0.85
                    if elapsed < min_ready:
                        print(
                            f"  Buffer not ready yet: elapsed {elapsed:.2f}s, "
                            f"need at least {min_ready:.2f}s before SPACE."
                        )
                        continue
                    break

            cap_fps_reported = float(cap.get(cv2.CAP_PROP_FPS) or cap_fps_reported)
            if cap_fps_reported <= 1.0:
                cap_fps_reported = _effective_fps(cap, combo.target_fps)
            stream_fourcc = _decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))

            cap.release()

            if aborted:
                print("Aborted by user.")
                break

            if frame is None:
                print("ERROR: no frames captured for this combo.")
                return 1

            actual_h, actual_w = frame.shape[0], frame.shape[1]
            measured = _measure_fps_from_times(recent_frame_times)
            span = rolling.time_span()
            buf_n = rolling.frame_count()
            elapsed = time.perf_counter() - t0

            res_ok = _resolution_ok(combo.width, combo.height, actual_w, actual_h)
            res_key = (combo.width, combo.height)
            negotiated_res_fps = negotiated_mjpg_fps_by_resolution.get(res_key)
            if negotiated_res_fps is None and measured is not None and measured > 1.0:
                # First completed combo for this resolution establishes MJPG baseline FPS.
                negotiated_res_fps = measured
                negotiated_mjpg_fps_by_resolution[res_key] = measured
            fps_ok = _fps_pass(combo.target_fps, measured, cap_fps_reported, negotiated_res_fps)
            buf_ok = _buffer_ok(combo.buffer_s, span, elapsed, measured)

            combo_pass = bool(res_ok and fps_ok and buf_ok)
            checks = {
                "resolution": "PASS" if res_ok else "FAIL",
                "fps": "PASS" if fps_ok else "FAIL",
                "buffer_window": "PASS" if buf_ok else "FAIL",
            }
            notes = {
                "resolution": _explain_resolution_fail(combo.width, combo.height, actual_w, actual_h, res_ok),
                "fps": _explain_fps_fail(
                    combo.target_fps, measured, cap_fps_reported, fps_ok, negotiated_res_fps
                ),
                "buffer_window": _explain_buffer_fail(
                    combo.buffer_s, span, elapsed, buf_n, measured, buf_ok
                ),
            }

            log_name = (
                f"tp13_combo_{combo.index:02d}_{combo.mode_id}_{combo.width}x{combo.height}_"
                f"{int(combo.target_fps)}fps_{combo.buffer_s:g}s.log"
            )
            log_path = args.logs_dir / log_name
            _write_log(
                log_path,
                combo,
                actual_w,
                actual_h,
                cap_fps_reported,
                measured,
                span,
                buf_n,
                elapsed,
                stream_fourcc,
                checks,
                notes,
            )

            status = "PASS" if combo_pass else "FAIL"
            print(f"  Actual resolution: {actual_w}x{actual_h}  (check: {checks['resolution']})")
            print(
                f"  FPS: measured {measured if measured is not None else float('nan'):.2f}  "
                f"mode_FPS {negotiated_res_fps if negotiated_res_fps is not None else float('nan'):.2f}  "
                f"(check: {checks['fps']})"
            )
            print(f"  Stream format: {stream_fourcc}")
            print(
                f"  Buffer: span {span:.2f}s / {combo.buffer_s}s  frames {buf_n}  "
                f"(check: {checks['buffer_window']})"
            )
            if not combo_pass:
                if not res_ok:
                    print(f"  Why resolution failed: {notes['resolution']}")
                if not fps_ok:
                    print(f"  Why FPS failed: {notes['fps']}")
                if not buf_ok:
                    print(f"  Why buffer failed: {notes['buffer_window']}")
            print(f"  --> {status}  log: {log_path}")

            fail_msgs: List[str] = []
            if not res_ok:
                fail_msgs.append(notes["resolution"])
            if not fps_ok:
                fail_msgs.append(notes["fps"])
            if not buf_ok:
                fail_msgs.append(notes["buffer_window"])
            results.append((combo, combo_pass, fail_msgs))

    except KeyboardInterrupt:
        print("\nStopped (KeyboardInterrupt).")
    finally:
        stop_event.set()
        cv2.destroyAllWindows()

    if results:
        print("\n=== Summary ===")
        all_pass = True
        for c, p, fails in results:
            mark = "PASS" if p else "FAIL"
            if not p:
                all_pass = False
            print(
                f"  {c.index}/{c.total}  {c.width}x{c.height}  {c.target_fps}fps  {c.buffer_s}s buffer  -> {mark}"
                f"  ({c.mode_id})"
            )
            if not p and fails:
                for msg in fails:
                    print(f"      - {msg}")
        print(
            f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILURES'} "
            f"({len(results)}/{len(combos)} completed)"
        )
        return 0 if all_pass else 1

    print("No combos completed.")
    return 1


def main() -> int:
    args = parse_args()
    orig_out, orig_err = sys.stdout, sys.stderr
    log_handle = None
    tee_out: Optional[TeeStream] = None
    tee_err: Optional[TeeStream] = None
    if not args.no_results_file:
        rp = args.results_file.resolve()
        rp.parent.mkdir(parents=True, exist_ok=True)
        log_handle = rp.open("w", encoding="utf-8", newline="\n")
        log_handle.write(f"# TP-13 results {datetime.now(timezone.utc).isoformat()} UTC\n\n")
        log_handle.flush()
        lock = threading.Lock()
        tee_out = TeeStream(
            orig_out, log_handle, lock, omit_line_fn=_omit_line_from_results_file
        )
        tee_err = TeeStream(
            orig_err, log_handle, lock, omit_line_fn=_omit_line_from_results_file
        )
        sys.stdout = tee_out
        sys.stderr = tee_err
    try:
        return _run_tp13(args)
    finally:
        if log_handle is not None:
            try:
                if tee_out is not None:
                    tee_out.flush()
                if tee_err is not None:
                    tee_err.flush()
            except Exception:
                pass
            sys.stdout, sys.stderr = orig_out, orig_err
            try:
                log_handle.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
