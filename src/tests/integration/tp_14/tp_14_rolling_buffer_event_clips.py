"""
TP-14: Rolling buffer and event-triggered clip extraction (manual integration test).

Maintains an in-memory rolling buffer of recent frames. Each stored frame is
burned in with a wall-clock timestamp (same style as preview) so saved MP4s
support manual inspection against the live preview. When you trigger an event
(keyboard), writes one full clip: pre-event frames from the buffer plus post-event
frames captured after the trigger. Saves under ./clips/ next to this script.

Optional dependency for global keypress detection: pip install pynput
Without pynput, press Enter in this console to trigger an event.
"""

from __future__ import annotations

import argparse
import csv
import math
import queue
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CLIPS_DIR = SCRIPT_DIR / "clips"
TOTAL_EVENTS = 3
PREVIEW_WINDOW = "TP-14 Preview"
MIN_PRE_EVENT_SECONDS = 5.0
MIN_POST_EVENT_SECONDS = 5.0


@dataclass
class ClipEvent:
    """One user-triggered clip capture."""

    index: int
    total: int
    triggered_at: datetime
    clip_path: Path
    pre_frame_count: int
    post_frame_count: int
    fps_used: float
    pre_seconds_est: float
    post_seconds_est: float
    total_seconds_est: float
    clip_readable: bool
    clip_duration_seconds: Optional[float]
    pre_coverage_ok: bool
    post_coverage_ok: bool
    continuity_ok: bool
    note: str = ""

    def __str__(self) -> str:
        return (
            f"ClipEvent {self.index}/{self.total} at {self.triggered_at.isoformat()} "
            f"-> {self.clip_path} "
            f"(pre={self.pre_seconds_est:.2f}s, post={self.post_seconds_est:.2f}s, "
            f"clip={self.clip_duration_seconds if self.clip_duration_seconds is not None else float('nan'):.2f}s)"
            + (f" [{self.note}]" if self.note else "")
        )


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

    def snapshot_frames(self) -> List[np.ndarray]:
        return [f for _, f in self._frames]

    def clear(self) -> None:
        self._frames.clear()


@dataclass
class ActiveClip:
    writer: "cv2.VideoWriter"
    post_wall_deadline: float
    min_post_frames: int
    event_index: int
    out_path: Path
    pre_frame_count: int
    trigger_wall: datetime
    trigger_monotonic: float
    post_frame_count: int = 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="TP-14: rolling buffer + keyboard-triggered event clips (3 events)."
    )
    p.add_argument(
        "--buffer-duration",
        type=float,
        default=10.0,
        help="Rolling buffer length in seconds (default: 10).",
    )
    p.add_argument(
        "--post-event-seconds",
        type=float,
        default=5.0,
        help="How many seconds to record after each trigger (default: 5).",
    )
    p.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index (default: 0).",
    )
    p.add_argument(
        "--clips-dir",
        type=Path,
        default=DEFAULT_CLIPS_DIR,
        help=f"Directory for clip files (default: {DEFAULT_CLIPS_DIR}).",
    )
    p.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Nominal FPS for VideoWriter when camera FPS is unavailable (default: 30).",
    )
    return p.parse_args()


def _open_writer(
    path: Path,
    frame_size: Tuple[int, int],
    fps: float,
) -> cv2.VideoWriter:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, frame_size)
    if not writer.isOpened():
        raise RuntimeError(f"Could not open VideoWriter for {path}")
    return writer


def _effective_fps(cap: cv2.VideoCapture, fallback: float) -> float:
    v = cap.get(cv2.CAP_PROP_FPS)
    if v is not None and v > 1.0:
        return float(v)
    return fallback


def _probe_clip_duration_seconds(path: Path) -> Optional[float]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps > 1e-6 and frame_count > 0:
            return frame_count / fps
        return None
    finally:
        cap.release()


def _burn_in_timestamp(bgr: np.ndarray, when: Optional[datetime] = None) -> np.ndarray:
    """Return a copy of the frame with wall-clock text burned in (used for buffer + saved clips)."""
    out = bgr.copy()
    ts = (when or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(out, ts, (20, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2, cv2.LINE_AA)
    return out


def _overlay_preview_hud(
    stamped_bgr: np.ndarray, status: str, events_done: int, total_events: int
) -> np.ndarray:
    """Preview-only HUD on top of a frame that already has the timestamp burn-in."""
    vis = stamped_bgr.copy()
    cv2.putText(
        vis,
        f"Events: {events_done}/{total_events} | SPACE/ENTER=trigger | Q=quit",
        (20, 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        vis,
        status,
        (20, 108),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return vis


def _write_event_report_csv(clips_dir: Path, events: List[ClipEvent]) -> Path:
    report_path = clips_dir / "tp14_event_report.csv"
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "event_index",
                "triggered_at",
                "clip_path",
                "pre_frame_count",
                "post_frame_count",
                "fps_used",
                "pre_seconds_est",
                "post_seconds_est",
                "total_seconds_est",
                "clip_readable",
                "clip_duration_seconds",
                "pre_coverage_ok",
                "post_coverage_ok",
                "continuity_ok",
                "note",
            ]
        )
        for e in events:
            writer.writerow(
                [
                    e.index,
                    e.triggered_at.isoformat(),
                    str(e.clip_path),
                    e.pre_frame_count,
                    e.post_frame_count,
                    f"{e.fps_used:.4f}",
                    f"{e.pre_seconds_est:.4f}",
                    f"{e.post_seconds_est:.4f}",
                    f"{e.total_seconds_est:.4f}",
                    e.clip_readable,
                    "" if e.clip_duration_seconds is None else f"{e.clip_duration_seconds:.4f}",
                    e.pre_coverage_ok,
                    e.post_coverage_ok,
                    e.continuity_ok,
                    e.note,
                ]
            )
    return report_path


def _stdin_trigger_thread(q: "queue.Queue[None]", stop: threading.Event) -> None:
    print("Enter-trigger mode: press Enter in this window to fire an event.")
    while not stop.is_set():
        try:
            sys.stdin.readline()
        except (EOFError, OSError):
            break
        if stop.is_set():
            break
        q.put(None)


def _pynput_trigger_thread(q: "queue.Queue[None]", stop: threading.Event) -> None:
    try:
        from pynput import keyboard
    except ImportError:
        return

    def on_press(_key: object) -> None:
        if not stop.is_set():
            q.put(None)

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    stop.wait()
    listener.stop()


def main() -> int:
    args = parse_args()
    args.clips_dir.mkdir(parents=True, exist_ok=True)

    trigger_q: queue.Queue[None] = queue.Queue()
    stop_event = threading.Event()

    use_pynput = False
    try:
        import pynput  # noqa: F401

        use_pynput = True
    except ImportError:
        pass

    if use_pynput:
        print("Keyboard mode: press almost any key to trigger an event (3 total).")
        t = threading.Thread(
            target=_pynput_trigger_thread, args=(trigger_q, stop_event), daemon=True
        )
        t.start()
    else:
        print("pynput not installed; using Enter to trigger. Install with: pip install pynput")
        t = threading.Thread(
            target=_stdin_trigger_thread, args=(trigger_q, stop_event), daemon=True
        )
        t.start()

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        print(f"ERROR: could not open camera index {args.camera_index}")
        stop_event.set()
        return 1

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    fps = _effective_fps(cap, args.fps)

    rolling = RollingFrameBuffer(args.buffer_duration)
    clips_finished = 0
    active: Optional[ActiveClip] = None
    triggers_used = 0
    completed_events: List[ClipEvent] = []

    print(
        f"Rolling buffer: {args.buffer_duration}s | post-event: {args.post_event_seconds}s | "
        f"FPS≈{fps:.2f} | clips -> {args.clips_dir.resolve()}"
    )
    print(
        f"Trigger exactly {TOTAL_EVENTS} events while performing a visible action in-frame (for example, wave)."
    )
    print(
        f"Pass targets per clip: pre >= {MIN_PRE_EVENT_SECONDS:.0f}s and post >= {MIN_POST_EVENT_SECONDS:.0f}s.\n"
    )
    cv2.namedWindow(PREVIEW_WINDOW, cv2.WINDOW_NORMAL)

    try:
        while clips_finished < TOTAL_EVENTS or active is not None:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("WARN: frame grab failed, retrying...")
                time.sleep(0.01)
                continue

            now = time.perf_counter()
            wall = datetime.now()
            stamped = _burn_in_timestamp(frame, wall)
            rolling.push(now, stamped)

            if active is not None:
                active.writer.write(stamped)
                active.post_frame_count += 1
                wall_elapsed_ok = now >= active.post_wall_deadline
                frames_ok = active.post_frame_count >= active.min_post_frames
                if wall_elapsed_ok and frames_ok:
                    active.writer.release()
                    pre_seconds = active.pre_frame_count / fps if fps > 1e-6 else 0.0
                    post_seconds = active.post_frame_count / fps if fps > 1e-6 else 0.0
                    total_est = pre_seconds + post_seconds
                    clip_duration = _probe_clip_duration_seconds(active.out_path)
                    clip_readable = clip_duration is not None
                    pre_ok = pre_seconds >= MIN_PRE_EVENT_SECONDS
                    post_ok = post_seconds >= MIN_POST_EVENT_SECONDS
                    continuity_ok = False
                    if clip_readable:
                        # Accept small encoder/container variance vs frame-count estimate.
                        continuity_ok = abs(clip_duration - total_est) <= max(1.0, 0.20 * total_est)
                    note_parts: List[str] = []
                    if not pre_ok:
                        note_parts.append("pre-event coverage < 5s")
                    if not post_ok:
                        note_parts.append("post-event coverage < 5s")
                    if not clip_readable:
                        note_parts.append("clip unreadable")
                    elif not continuity_ok:
                        note_parts.append("duration mismatch suggests discontinuity")
                    ev = ClipEvent(
                        index=active.event_index,
                        total=TOTAL_EVENTS,
                        triggered_at=active.trigger_wall,
                        clip_path=active.out_path,
                        pre_frame_count=active.pre_frame_count,
                        post_frame_count=active.post_frame_count,
                        fps_used=fps,
                        pre_seconds_est=pre_seconds,
                        post_seconds_est=post_seconds,
                        total_seconds_est=total_est,
                        clip_readable=clip_readable,
                        clip_duration_seconds=clip_duration,
                        pre_coverage_ok=pre_ok,
                        post_coverage_ok=post_ok,
                        continuity_ok=continuity_ok,
                        note="; ".join(note_parts),
                    )
                    print(f"SAVED {active.event_index}/{TOTAL_EVENTS}: {ev}")
                    completed_events.append(ev)
                    clips_finished += 1
                    active = None

            while True:
                try:
                    trigger_q.get_nowait()
                except queue.Empty:
                    break

                if triggers_used >= TOTAL_EVENTS:
                    print("WARN: all 3 events already used; extra trigger ignored.")
                    continue
                if active is not None:
                    print("WARN: clip is being written; trigger ignored.")
                    continue

                triggers_used += 1
                pre_frames = rolling.snapshot_frames()
                triggered_at = datetime.now()
                stamp = triggered_at.strftime("%Y%m%d_%H%M%S")
                out_path = args.clips_dir / (
                    f"tp14_event_{triggers_used}of{TOTAL_EVENTS}_{stamp}.mp4"
                )

                h, w = stamped.shape[:2]
                writer = _open_writer(out_path, (w, h), fps)
                for f in pre_frames:
                    writer.write(f)

                min_post = max(1, math.ceil(args.post_event_seconds * fps - 1e-9))
                active = ActiveClip(
                    writer=writer,
                    post_wall_deadline=now + args.post_event_seconds,
                    min_post_frames=min_post,
                    event_index=triggers_used,
                    out_path=out_path,
                    pre_frame_count=len(pre_frames),
                    trigger_wall=triggered_at,
                    trigger_monotonic=now,
                )

                pending = ClipEvent(
                    index=triggers_used,
                    total=TOTAL_EVENTS,
                    triggered_at=triggered_at,
                    clip_path=out_path,
                    pre_frame_count=len(pre_frames),
                    post_frame_count=0,
                    fps_used=fps,
                    pre_seconds_est=len(pre_frames) / fps if fps > 1e-6 else 0.0,
                    post_seconds_est=0.0,
                    total_seconds_est=0.0,
                    clip_readable=False,
                    clip_duration_seconds=None,
                    pre_coverage_ok=False,
                    post_coverage_ok=False,
                    continuity_ok=False,
                    note="post recording…",
                )
                print(f"EVENT {triggers_used}/{TOTAL_EVENTS}: {pending}")

            status = (
                f"Capturing post-event clip {active.event_index}/{TOTAL_EVENTS}"
                if active is not None
                else "Ready for next trigger - perform visible action and press SPACE/ENTER"
            )
            vis = _overlay_preview_hud(stamped, status, clips_finished, TOTAL_EVENTS)
            cv2.imshow(PREVIEW_WINDOW, vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == ord("Q"):
                print("Quit requested from preview window.")
                break
            if key == ord(" ") or key == 13:
                trigger_q.put(None)

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        stop_event.set()
        if active is not None:
            active.writer.release()
        cap.release()
        cv2.destroyAllWindows()

    if clips_finished == TOTAL_EVENTS:
        report_path = _write_event_report_csv(args.clips_dir, completed_events)
        print(f"\nTP-14 run complete: {clips_finished} clip(s) in {args.clips_dir.resolve()}")
        print(f"Verification report: {report_path}")
        all_checks_pass = all(
            e.pre_coverage_ok and e.post_coverage_ok and e.continuity_ok for e in completed_events
        )
        print(f"Automated check result: {'PASS' if all_checks_pass else 'FAIL'}")
        for e in completed_events:
            mark = (
                "PASS"
                if (e.pre_coverage_ok and e.post_coverage_ok and e.continuity_ok)
                else "FAIL"
            )
            print(
                f"  Event {e.index}: {mark} | pre={e.pre_seconds_est:.2f}s "
                f"post={e.post_seconds_est:.2f}s clip={e.clip_duration_seconds if e.clip_duration_seconds is not None else float('nan'):.2f}s"
            )
            if e.note:
                print(f"    note: {e.note}")
        return 0 if all_checks_pass else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
