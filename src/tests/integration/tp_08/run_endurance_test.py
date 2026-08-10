#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2
except ImportError as _e:  # pragma: no cover
    cv2 = None  # type: ignore

try:
    import psutil  # type: ignore
except Exception:
    psutil = None


TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_EVENT_TOTAL = 8

PREVIEW_WINDOW = "TP-08 preview (q = quit)"
PREVIEW_MAX_WIDTH = 960
PREVIEW_MAX_HEIGHT = 540
PREVIEW_WINDOW_X = 40
PREVIEW_WINDOW_Y = 60
DEFAULT_FFMPEG_CRF = 20
SETPTS_RATIO_EPSILON = 0.02

ALLOWED_CAMERA_MODE_IDS = frozenset({"mjpeg_1280x720_30", "mjpeg_800x600_30", "mjpeg_640x480_30"})

POSSIBLE_TP08_FAILURES = [
    "Python endurance harness terminated early",
    "Unhandled exception interrupted logging or clip orchestration",
    "Heartbeat logging stopped before the configured duration elapsed",
    "Total elapsed runtime was shorter than the configured duration",
    "Recording step failed badly enough that endurance could not continue",
    "System resource or power issues prevented continued operation",
]

POSSIBLE_TP08_RECORDING_FAILURES = [
    "Clip file was not created",
    "Clip file was empty",
    "Recording step returned a nonzero exit code",
    "Recorded coverage (intended clip plan, wall-clock span, or run elapsed) was shorter than the configured total duration",
    "Storage exhaustion or write interruption occurred during the run",
    "Camera capture or recording stopped unexpectedly mid-run",
]

POSSIBLE_TP09_FAILURES = [
    "No internal temperature samples were recorded",
    "No outside temperature samples were recorded",
    "Peak internal Pi temperature exceeded the limit",
    "Average internal Pi temperature was not below the limit",
    "Average outside air temperature was below the required minimum",
]

TP09_MAX_INTERNAL_TEMP_C = 85.0
TP09_AVG_INTERNAL_TEMP_C_LIMIT = 82.0
TP09_MIN_AVG_OUTSIDE_TEMP_F = 80.0


@dataclass
class Config:
    evidence_root: Path
    total_record_seconds: int
    clip_divisions: int
    check_interval_seconds: int
    recording_grace_period: int
    v4l2_device: str
    v4l2_buffer_frames: int
    camera_mode_id: str
    catalog_width: int
    catalog_height: int
    catalog_fps: float
    preview_enabled: bool
    preview_rotation_degrees: int
    preview_info_enabled: bool
    stop_on_clip_failure: bool
    fix_playback_timing: bool
    ffmpeg_crf: int
    outside_temp_f: Optional[float]
    outside_temp_file: Optional[Path]
    tp09_max_internal_temp_c: float
    tp09_avg_internal_temp_c_limit: float
    tp09_min_avg_outside_temp_f: float


@dataclass
class ClipPlan:
    index: int
    duration_seconds: int


@dataclass
class ClipResult:
    clip_index: int
    clip_name: str
    output_path: Path
    format_used: str
    start_time: str
    end_time: str
    intended_duration_sec: int
    return_code: Optional[int]
    file_exists: bool
    file_nonzero_bytes: bool
    notes: str


@dataclass
class RecordingCoverage:
    intended_clip_seconds: int
    wall_clock_span_sec: int
    run_elapsed_sec: int
    effective_coverage_sec: float
    coverage_metric: str


@dataclass
class RuntimeSample:
    timestamp: str
    elapsed_sec: int
    heartbeat_ok: bool
    active_clip_index: Optional[int]
    recording_process_alive: bool
    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    notes: str


@dataclass
class TemperatureSample:
    timestamp: str
    elapsed_sec: int
    internal_temp_c: Optional[float]
    outside_temp_f: Optional[float]


def parse_wall_timestamp(value: str) -> Optional[datetime]:
    try:
        return datetime.strptime(value, TIMESTAMP_FMT)
    except Exception:
        return None


def wall_clock_span_from_clips(clip_results: List[ClipResult]) -> int:
    starts = [parse_wall_timestamp(r.start_time) for r in clip_results if r.start_time]
    ends = [parse_wall_timestamp(r.end_time) for r in clip_results if r.end_time]
    starts = [t for t in starts if t is not None]
    ends = [t for t in ends if t is not None]
    if not starts or not ends:
        return 0
    return max(0, int((max(ends) - min(starts)).total_seconds()))


def intended_duration_sum(clip_results: List[ClipResult]) -> int:
    good = [
        r
        for r in clip_results
        if r.file_exists
        and r.file_nonzero_bytes
        and (r.return_code is None or r.return_code == 0)
    ]
    return sum(r.intended_duration_sec for r in good if r.intended_duration_sec > 0)


def compute_recording_coverage(
    clip_results: List[ClipResult],
    recording_grace_period: int,
    run_elapsed_sec: Optional[int] = None,
) -> RecordingCoverage:
    intended = intended_duration_sum(clip_results)
    wall = wall_clock_span_from_clips(clip_results)
    run_el = max(0, int(run_elapsed_sec or 0))

    candidates: Dict[str, float] = {
        "intended_clip_plan": float(intended),
        "wall_clock_span": float(wall),
    }
    if run_el > 0:
        candidates["run_elapsed_plus_grace"] = float(run_el + recording_grace_period)

    metric, effective = max(candidates.items(), key=lambda item: item[1])
    return RecordingCoverage(
        intended_clip_seconds=intended,
        wall_clock_span_sec=wall,
        run_elapsed_sec=run_el,
        effective_coverage_sec=effective,
        coverage_metric=metric,
    )


def format_recording_coverage_lines(coverage: RecordingCoverage, recording_grace_period: int) -> List[str]:
    return [
        f"Sum of intended clip durations (successful clips): {coverage.intended_clip_seconds} sec",
        f"Wall-clock span (first clip start to last clip end): {coverage.wall_clock_span_sec} sec",
        f"Run elapsed (harness): {coverage.run_elapsed_sec} sec",
        f"Effective coverage used for pass/fail: {coverage.effective_coverage_sec:.2f} sec ({coverage.coverage_metric})",
        f"Recording grace period: {recording_grace_period} sec",
    ]


def evaluate_tp08_recording(
    clip_results: List[ClipResult],
    total_record_seconds: int,
    recording_grace_period: int,
    run_elapsed_sec: Optional[int] = None,
) -> Tuple[str, str, List[str], RecordingCoverage]:
    possible_failures = list(POSSIBLE_TP08_RECORDING_FAILURES)
    coverage = compute_recording_coverage(clip_results, recording_grace_period, run_elapsed_sec)
    if not clip_results:
        return "FAIL", "No clip results were recorded", possible_failures, coverage

    missing = [r for r in clip_results if not r.file_exists]
    empty = [r for r in clip_results if not r.file_nonzero_bytes]
    bad_return = [r for r in clip_results if r.return_code not in (None, 0)]

    if missing:
        return (
            "FAIL",
            f"{len(missing)} clip(s) were not created: {', '.join(r.clip_name for r in missing)}",
            possible_failures,
            coverage,
        )
    if empty:
        return (
            "FAIL",
            f"{len(empty)} clip(s) were empty: {', '.join(r.clip_name for r in empty)}",
            possible_failures,
            coverage,
        )
    if bad_return:
        return (
            "FAIL",
            f"{len(bad_return)} clip(s) had a nonzero recording return code: {', '.join(r.clip_name for r in bad_return)}",
            possible_failures,
            coverage,
        )
    if coverage.effective_coverage_sec + 1.0 < total_record_seconds:
        return (
            "FAIL",
            (
                f"Best coverage metric {coverage.coverage_metric} = {coverage.effective_coverage_sec:.2f}s "
                f"(intended plan {coverage.intended_clip_seconds}s; wall span {coverage.wall_clock_span_sec}s; "
                f"run elapsed {coverage.run_elapsed_sec}s), which was shorter than configured duration "
                f"{total_record_seconds}s"
            ),
            possible_failures,
            coverage,
        )
    return (
        "PASS",
        (
            f"Segmented recording met the configured duration using {coverage.coverage_metric} "
            f"({coverage.effective_coverage_sec:.2f}s vs {total_record_seconds}s target)."
        ),
        possible_failures,
        coverage,
    )


def evaluate_tp09_heat(
    samples: List[TemperatureSample],
    min_avg_outside_f: float = TP09_MIN_AVG_OUTSIDE_TEMP_F,
    max_internal_c: float = TP09_MAX_INTERNAL_TEMP_C,
    max_avg_internal_c: float = TP09_AVG_INTERNAL_TEMP_C_LIMIT,
) -> Tuple[str, str, List[str]]:
    possible_failures = list(POSSIBLE_TP09_FAILURES)
    internal = [s.internal_temp_c for s in samples if s.internal_temp_c is not None]
    outside = [s.outside_temp_f for s in samples if s.outside_temp_f is not None]

    if not internal:
        return "FAIL", "No internal temperature samples were recorded", possible_failures

    peak_internal = max(internal)
    if peak_internal > max_internal_c:
        return (
            "FAIL",
            f"Peak internal temperature {peak_internal:.2f} °C exceeded limit {max_internal_c} °C",
            possible_failures,
        )

    avg_internal = sum(internal) / len(internal)
    if avg_internal >= max_avg_internal_c:
        return (
            "FAIL",
            f"Average internal temperature {avg_internal:.2f} °C was not below {max_avg_internal_c} °C",
            possible_failures,
        )

    if not outside:
        return (
            "FAIL",
            "No outside temperature samples were recorded (set outside_temp_f or outside_temp_file in config)",
            possible_failures,
        )

    avg_outside = sum(outside) / len(outside)
    if avg_outside < min_avg_outside_f:
        return (
            "FAIL",
            f"Average outside temperature {avg_outside:.1f} °F was below {min_avg_outside_f} °F",
            possible_failures,
        )

    return (
        "PASS",
        (
            f"Thermal limits met: peak internal {peak_internal:.2f} °C, "
            f"average internal {avg_internal:.2f} °C, average outside {avg_outside:.1f} °F"
        ),
        possible_failures,
    )


def write_pass_fail(
    path: Path,
    test_id: str,
    status: str,
    reason: str,
    criteria_lines: List[str],
    detail_lines: Optional[List[str]] = None,
) -> None:
    lines = [
        f"{test_id}: {status}",
        "",
        f"Result: {reason}",
        "",
        "Pass criteria checked:",
        *[f"- {line}" for line in criteria_lines],
    ]
    if detail_lines:
        lines.extend(["", "Details:", *[f"- {line}" for line in detail_lines]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_clip_duration_plan(total_record_seconds: int, clip_divisions: int) -> Dict[int, int]:
    base = total_record_seconds // clip_divisions
    remainder = total_record_seconds % clip_divisions
    if base <= 0:
        return {}
    plan: Dict[int, int] = {}
    for i in range(1, clip_divisions + 1):
        plan[i] = base + (remainder if i == clip_divisions else 0)
    return plan


def _rotate_frame(frame: Any, degrees: int) -> Any:
    d = degrees % 360
    if d == 0:
        return frame
    if d == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if d == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if d == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"preview_rotation_degrees must be 0, 90, 180, or 270; got {degrees}")


def _preview_size(fw: int, fh: int, mx: int, my: int) -> Tuple[int, int]:
    if fw <= mx and fh <= my:
        return fw, fh
    s = min(mx / fw, my / fh)
    return max(1, int(round(fw * s))), max(1, int(round(fh * s)))


def remux_clip_playback_timing(
    tmp_path: Path,
    output_path: Path,
    catalog_fps: float,
    frames_written: int,
    wall_elapsed_sec: float,
    crf: int,
) -> Tuple[bool, str]:
    """Stretch/compress timestamps so playback duration matches wall time (TP-04 setpts)."""
    if frames_written <= 0 or wall_elapsed_sec <= 0:
        return False, "no frames or elapsed time for timing fix"
    actual_fps = frames_written / wall_elapsed_sec
    ratio = catalog_fps / actual_fps if actual_fps > 1e-6 else 1.0
    if abs(ratio - 1.0) <= SETPTS_RATIO_EPSILON:
        try:
            if output_path.exists():
                output_path.unlink()
            os.replace(tmp_path, output_path)
        except OSError as exc:
            return False, f"could not move temp clip: {exc}"
        return True, f"timing ok (catalog {catalog_fps:g} fps, sustained {actual_fps:.2f} fps)"

    out_fps = max(1, int(round(catalog_fps)))
    vf = f"setpts=PTS*{ratio:.8f},fps={out_fps}"
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        str(tmp_path),
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-level:v",
        "4.2",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return False, "ffmpeg not found on PATH"
    except Exception as exc:
        return False, f"ffmpeg failed: {exc}"
    if result.returncode != 0:
        err = (result.stderr or "").strip() or f"ffmpeg exit {result.returncode}"
        return False, err
    try:
        tmp_path.unlink(missing_ok=True)
    except OSError:
        pass
    return (
        True,
        f"setpts x {ratio:.4f} ({frames_written} frames / {wall_elapsed_sec:.1f}s wall = "
        f"{actual_fps:.2f} fps vs catalog {catalog_fps:g} fps header)",
    )


class EnduranceRunner:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.event_counter = 0
        self.start_monotonic = 0.0
        self.end_monotonic = 0.0
        self.test_start_wall = ""
        self.test_end_wall = ""
        self.received_stop_signal = False
        self.all_clip_results: List[ClipResult] = []
        self.runtime_samples: List[RuntimeSample] = []
        self.temperature_samples: List[TemperatureSample] = []
        self.used_formats: List[str] = []
        self.failure_messages: List[str] = []

        self.tp08_dir = self.config.evidence_root / "TP-08"
        self.tp09_dir = self.config.evidence_root / "TP-09"
        self.tp08_clips_dir = self.tp08_dir / "clips"
        self.tp08_pass_fail = self.tp08_dir / "pass_fail.txt"
        self.tp09_pass_fail = self.tp09_dir / "pass_fail.txt"
        self.runtime_log = self.tp08_dir / "runtime_log.csv"
        self.event_log = self.tp08_dir / "event_log.txt"
        self.storage_log = self.tp08_dir / "storage_log.csv"
        self.recording_log = self.tp08_dir / "recording_log.csv"
        self.temperature_log = self.tp09_dir / "temperature_log.csv"

    @staticmethod
    def load_config(path: Path) -> Config:
        with path.open("r", encoding="utf-8-sig") as f:
            raw = json.load(f)

        required_keys = [
            "evidence_root",
            "total_record_seconds",
            "clip_divisions",
            "check_interval_seconds",
            "recording_grace_period",
            "preview_enabled",
            "preview_rotation_degrees",
            "preview_info_enabled",
            "stop_on_clip_failure",
            "camera_modes",
            "camera_mode_id",
        ]
        missing = [k for k in required_keys if k not in raw]
        if missing:
            raise ValueError(f"Missing config keys: {', '.join(missing)}")

        evidence_root = Path(raw["evidence_root"]).expanduser()
        if not evidence_root.is_absolute():
            raise ValueError("evidence_root must be an absolute path")

        rotation = int(raw["preview_rotation_degrees"])
        if rotation not in {0, 90, 180, 270}:
            raise ValueError("preview_rotation_degrees must be 0, 90, 180, or 270")

        clip_divisions = int(raw["clip_divisions"])
        if clip_divisions <= 0:
            raise ValueError("clip_divisions must be greater than 0")

        total_record_seconds = int(raw["total_record_seconds"])
        if total_record_seconds <= 0:
            raise ValueError("total_record_seconds must be greater than 0")

        check_interval_seconds = int(raw["check_interval_seconds"])
        if check_interval_seconds <= 0:
            raise ValueError("check_interval_seconds must be greater than 0")

        recording_grace_period = int(raw["recording_grace_period"])
        if recording_grace_period < 0:
            raise ValueError("recording_grace_period must be 0 or greater")

        camera_modes = raw["camera_modes"]
        if not isinstance(camera_modes, list) or len(camera_modes) == 0:
            raise ValueError("camera_modes must be a non-empty array")

        mode_by_id: Dict[str, Dict[str, Any]] = {}
        for m in camera_modes:
            if not isinstance(m, dict):
                raise ValueError("each camera_modes entry must be an object")
            mid = str(m.get("id", ""))
            if mid not in ALLOWED_CAMERA_MODE_IDS:
                raise ValueError(f"Unsupported camera mode id {mid!r}; allowed: {sorted(ALLOWED_CAMERA_MODE_IDS)}")
            if str(m.get("input_format", "")).lower() != "mjpeg":
                raise ValueError(f"Mode {mid} must use input_format mjpeg for TP-08")
            for key in ("width", "height", "fps"):
                if key not in m:
                    raise ValueError(f"Mode {mid} missing {key}")
            mode_by_id[mid] = m

        if len(mode_by_id) != len(ALLOWED_CAMERA_MODE_IDS):
            raise ValueError(
                f"camera_modes must include exactly these ids: {sorted(ALLOWED_CAMERA_MODE_IDS)}"
            )

        camera_mode_id = str(raw["camera_mode_id"])
        if camera_mode_id not in mode_by_id:
            raise ValueError(
                f"camera_mode_id {camera_mode_id!r} not found in camera_modes (ids: {sorted(mode_by_id)})"
            )

        active = mode_by_id[camera_mode_id]
        catalog_width = int(active["width"])
        catalog_height = int(active["height"])
        catalog_fps = float(active["fps"])

        v4l2_device = str(raw.get("v4l2_device", "")).strip()
        if not v4l2_device:
            idx = int(raw.get("camera_index", 0))
            v4l2_device = f"/dev/video{idx}"

        v4l2_buffer_frames = int(raw.get("v4l2_buffer_frames", 1))
        if v4l2_buffer_frames < 1:
            raise ValueError("v4l2_buffer_frames must be >= 1")

        outside_temp_f: Optional[float] = None
        if "outside_temp_f" in raw and raw["outside_temp_f"] is not None:
            outside_temp_f = float(raw["outside_temp_f"])

        outside_temp_file: Optional[Path] = None
        if raw.get("outside_temp_file"):
            outside_temp_file = Path(str(raw["outside_temp_file"])).expanduser()

        return Config(
            evidence_root=evidence_root,
            total_record_seconds=total_record_seconds,
            clip_divisions=clip_divisions,
            check_interval_seconds=check_interval_seconds,
            recording_grace_period=recording_grace_period,
            v4l2_device=v4l2_device,
            v4l2_buffer_frames=v4l2_buffer_frames,
            camera_mode_id=camera_mode_id,
            catalog_width=catalog_width,
            catalog_height=catalog_height,
            catalog_fps=catalog_fps,
            preview_enabled=bool(raw["preview_enabled"]),
            preview_rotation_degrees=rotation,
            preview_info_enabled=bool(raw["preview_info_enabled"]),
            stop_on_clip_failure=bool(raw["stop_on_clip_failure"]),
            fix_playback_timing=bool(raw.get("fix_playback_timing", True)),
            ffmpeg_crf=int(raw.get("ffmpeg_crf", DEFAULT_FFMPEG_CRF)),
            outside_temp_f=outside_temp_f,
            outside_temp_file=outside_temp_file,
            tp09_max_internal_temp_c=float(raw.get("tp09_max_internal_temp_c", TP09_MAX_INTERNAL_TEMP_C)),
            tp09_avg_internal_temp_c_limit=float(
                raw.get("tp09_avg_internal_temp_c_limit", TP09_AVG_INTERNAL_TEMP_C_LIMIT)
            ),
            tp09_min_avg_outside_temp_f=float(
                raw.get("tp09_min_avg_outside_temp_f", TP09_MIN_AVG_OUTSIDE_TEMP_F)
            ),
        )

    def ensure_structure(self) -> None:
        self.config.evidence_root.mkdir(parents=True, exist_ok=True)
        self.tp08_dir.mkdir(parents=True, exist_ok=True)
        self.tp09_dir.mkdir(parents=True, exist_ok=True)
        self.tp08_clips_dir.mkdir(parents=True, exist_ok=True)

    def init_logs(self) -> None:
        with self.runtime_log.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "elapsed_sec",
                    "heartbeat_ok",
                    "active_clip_index",
                    "recording_process_alive",
                    "cpu_percent",
                    "ram_percent",
                    "notes",
                ]
            )

        with self.temperature_log.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "elapsed_sec",
                    "internal_temp_c",
                    "outside_temp_f",
                ]
            )

        with self.storage_log.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "elapsed_sec",
                    "clip_index",
                    "clip_name",
                    "clip_exists",
                    "clip_size_bytes",
                    "total_clip_count",
                    "total_clip_size_bytes",
                    "disk_used_gb",
                    "disk_free_gb",
                    "notes",
                ]
            )

        with self.recording_log.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "clip_index",
                    "clip_name",
                    "format",
                    "start_time",
                    "end_time",
                    "intended_duration_sec",
                    "actual_process_return_code",
                    "file_exists",
                    "file_nonzero_bytes",
                    "notes",
                ]
            )

        self.event_log.write_text("", encoding="utf-8")

    def write_event(self, message: str, numbered: bool = False) -> None:
        prefix = ""
        if numbered:
            self.event_counter += 1
            prefix = f"({self.event_counter}/{DEFAULT_EVENT_TOTAL}) "
        line = f"[{self.now_str()}] {prefix}{message}\n"
        with self.event_log.open("a", encoding="utf-8") as f:
            f.write(line)
        print(line, end="")

    def now_str(self) -> str:
        return datetime.now().strftime(TIMESTAMP_FMT)

    def build_clip_plan(self) -> List[ClipPlan]:
        plan_map = build_clip_duration_plan(self.config.total_record_seconds, self.config.clip_divisions)
        if not plan_map:
            raise ValueError(
                "clip_divisions is too large for total_record_seconds; at least one clip would have 0 seconds"
            )
        return [ClipPlan(index=i, duration_seconds=plan_map[i]) for i in sorted(plan_map)]

    def install_signal_handlers(self) -> None:
        def handler(signum: int, _frame: Any) -> None:
            self.received_stop_signal = True
            self.write_event(f"Received stop signal {signum}; attempting graceful shutdown")

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)

    def run(self) -> int:
        self.install_signal_handlers()
        plan = self.build_clip_plan()
        self.ensure_structure()
        self.init_logs()

        self.start_monotonic = time.monotonic()
        self.test_start_wall = self.now_str()

        tp08_status = "FAIL"
        tp08_reason = "Pass/fail evaluation did not complete"
        tp09_status = "FAIL"
        tp09_reason = "Pass/fail evaluation did not complete"

        self.write_event("Test started", numbered=True)
        self.write_event("Configuration loaded and evidence directories initialized", numbered=True)
        self.write_event("Clip plan computed", numbered=True)
        self.write_event("Periodic heartbeat logging active", numbered=True)

        try:
            for clip in plan:
                if self.received_stop_signal:
                    self.failure_messages.append("Execution interrupted by signal before all clips completed")
                    break
                result = self.run_single_clip(clip, total_clips=len(plan))
                self.all_clip_results.append(result)
                if result.format_used not in self.used_formats:
                    self.used_formats.append(result.format_used)
                self.append_recording_log(result)
                self.append_storage_snapshot(clip.index, result.output_path, result.notes)
                if clip.index == max(1, math.ceil(len(plan) / 2)):
                    self.write_event("Mid-test recording progression confirmed", numbered=True)
                if (not result.file_exists or not result.file_nonzero_bytes) and self.config.stop_on_clip_failure:
                    self.failure_messages.append(
                        f"Stopped after clip {clip.index} due to stop_on_clip_failure=true"
                    )
                    break

            self.write_event("Final clip recording completed or attempted", numbered=True)
        except Exception as exc:
            self.failure_messages.append(f"Unhandled exception during run: {exc}")
            self.write_event(f"Unhandled exception during run: {exc}")
        finally:
            self.end_monotonic = time.monotonic()
            self.test_end_wall = self.now_str()
            tp08_status, tp08_reason, tp08_detail = self.evaluate_tp08_combined()
            tp09_status, tp09_reason, _ = self.evaluate_tp09_heat_run()
            self.write_event("Post-run verification completed", numbered=True)
            try:
                self.write_pass_fail_reports(tp08_status, tp08_reason, tp08_detail, tp09_status, tp09_reason)
                self.write_event("Pass/fail reports written", numbered=True)
            except Exception as exc:
                self.write_event(f"Pass/fail write failed: {exc}")
                raise

        return 0 if tp08_status == "PASS" and tp09_status == "PASS" else 1

    def run_single_clip(self, clip: ClipPlan, total_clips: int) -> ClipResult:
        clip_start = self.now_str()
        self.write_event(f"Clip {clip.index}/{total_clips} recording started")
        clip_name = f"clip_{clip.index:04d}.mp4"
        output_path = self.tp08_clips_dir / clip_name
        return_code, notes = self._record_clip_opencv(clip, total_clips, output_path)
        exists = output_path.exists()
        nonzero = exists and output_path.stat().st_size > 0
        if return_code != 0:
            notes = self.append_note(notes, f"Recording step exited with code {return_code}")
        return ClipResult(
            clip_index=clip.index,
            clip_name=clip_name,
            output_path=output_path,
            format_used="mp4",
            start_time=clip_start,
            end_time=self.now_str(),
            intended_duration_sec=clip.duration_seconds,
            return_code=return_code,
            file_exists=exists,
            file_nonzero_bytes=nonzero,
            notes=notes,
        )

    def _record_clip_opencv(
        self,
        clip: ClipPlan,
        total_clips: int,
        output_path: Path,
    ) -> Tuple[int, str]:
        if cv2 is None:
            return 1, "OpenCV (cv2) is not installed"

        cfg = self.config
        cap = cv2.VideoCapture(cfg.v4l2_device, cv2.CAP_V4L2)
        if not cap.isOpened():
            return 1, f"Cannot open V4L2 device {cfg.v4l2_device!r}"

        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(cfg.catalog_width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(cfg.catalog_height))
        cap.set(cv2.CAP_PROP_FPS, cfg.catalog_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, float(cfg.v4l2_buffer_frames))
        cap.read()

        ok, frame0 = cap.read()
        if not ok or frame0 is None:
            cap.release()
            return 1, "No frame from camera"

        out0 = _rotate_frame(frame0, cfg.preview_rotation_degrees)
        oh, ow = out0.shape[:2]
        tmp_path = Path(str(output_path) + ".tmp.mp4")
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(tmp_path), fourcc, cfg.catalog_fps, (ow, oh))
        if not writer.isOpened():
            cap.release()
            return 1, f"Cannot open VideoWriter for {tmp_path!r}"

        notes = ""
        clip_t0 = time.monotonic()
        deadline = clip_t0 + float(clip.duration_seconds)
        next_sample = time.monotonic()
        interval = float(cfg.check_interval_seconds)
        placed = False
        pw, ph = _preview_size(ow, oh, PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT)
        fps_ema: Optional[float] = None
        last_fps_tick = time.monotonic()
        frames_for_fps = 0
        frames_written = 0
        exit_code = 0

        if cfg.preview_enabled:
            cv2.namedWindow(PREVIEW_WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(PREVIEW_WINDOW, pw, ph)

        writer.write(out0)
        frames_written = 1
        frames_for_fps = 1

        try:
            while time.monotonic() < deadline and not self.received_stop_signal:
                now = time.monotonic()
                while now >= next_sample:
                    self.append_runtime_sample(
                        active_clip_index=clip.index,
                        recording_process_alive=True,
                        notes="heartbeat",
                    )
                    self.append_temperature_sample()
                    next_sample += interval
                    now = time.monotonic()

                ok, frame = cap.read()
                if not ok or frame is None:
                    notes = self.append_note(notes, "Stream ended or frame read failed")
                    exit_code = 1
                    break

                out = _rotate_frame(frame, cfg.preview_rotation_degrees)
                writer.write(out)
                frames_written += 1

                frames_for_fps += 1
                tnow = time.monotonic()
                if tnow - last_fps_tick >= 1.0:
                    inst = frames_for_fps / (tnow - last_fps_tick)
                    fps_ema = inst if fps_ema is None else (0.85 * fps_ema + 0.15 * inst)
                    frames_for_fps = 0
                    last_fps_tick = tnow

                if cfg.preview_enabled:
                    pv = cv2.resize(out, (pw, ph), interpolation=cv2.INTER_AREA)
                    cv2.imshow(PREVIEW_WINDOW, pv)
                    if not placed:
                        cv2.moveWindow(PREVIEW_WINDOW, PREVIEW_WINDOW_X, PREVIEW_WINDOW_Y)
                        placed = True
                    temp = self.get_temperature_c()
                    elapsed_clip = max(0.0, time.monotonic() - clip_t0)
                    title_parts = [f"TP-08 clip {clip.index}/{total_clips}"]
                    if cfg.preview_info_enabled:
                        title_parts.append(f"{elapsed_clip:.0f}s/{clip.duration_seconds}s")
                        if temp is not None:
                            title_parts.append(f"{temp:.0f}C")
                        if fps_ema is not None:
                            title_parts.append(f"~{fps_ema:.0f}fps")
                    try:
                        cv2.setWindowTitle(PREVIEW_WINDOW, " | ".join(title_parts))
                    except Exception:
                        pass
                    if (cv2.waitKey(1) & 0xFF) == ord("q"):
                        notes = self.append_note(notes, "Operator pressed q to end clip early")
                        exit_code = 2
                        break
                else:
                    time.sleep(0.02)

            if exit_code == 0 and self.received_stop_signal:
                notes = self.append_note(notes, "Interrupted by signal")
                exit_code = 130
        finally:
            writer.release()
            cap.release()
            if cfg.preview_enabled:
                try:
                    cv2.destroyWindow(PREVIEW_WINDOW)
                except Exception:
                    cv2.destroyAllWindows()

        wall_elapsed = time.monotonic() - clip_t0
        if exit_code == 0 and frames_written > 0 and tmp_path.exists() and tmp_path.stat().st_size > 0:
            if cfg.fix_playback_timing:
                ok, timing_note = remux_clip_playback_timing(
                    tmp_path,
                    output_path,
                    cfg.catalog_fps,
                    frames_written,
                    wall_elapsed,
                    cfg.ffmpeg_crf,
                )
                notes = self.append_note(notes, timing_note)
                if not ok:
                    notes = self.append_note(notes, "ffmpeg timing fix failed; kept raw mp4v temp as clip")
                    try:
                        if output_path.exists():
                            output_path.unlink()
                        os.replace(tmp_path, output_path)
                    except OSError as exc:
                        notes = self.append_note(notes, f"could not finalize clip file: {exc}")
                        exit_code = 1
            else:
                try:
                    if output_path.exists():
                        output_path.unlink()
                    os.replace(tmp_path, output_path)
                except OSError as exc:
                    notes = self.append_note(notes, f"could not move temp clip: {exc}")
                    exit_code = 1
        elif tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

        return exit_code, notes

    def append_note(self, existing: str, new_note: str) -> str:
        return new_note if not existing else f"{existing}; {new_note}"

    def append_runtime_sample(self, active_clip_index: Optional[int], recording_process_alive: bool, notes: str) -> None:
        sample = RuntimeSample(
            timestamp=self.now_str(),
            elapsed_sec=int(time.monotonic() - self.start_monotonic),
            heartbeat_ok=True,
            active_clip_index=active_clip_index,
            recording_process_alive=recording_process_alive,
            cpu_percent=self.get_cpu_percent(),
            ram_percent=self.get_ram_percent(),
            notes=notes,
        )
        self.runtime_samples.append(sample)
        with self.runtime_log.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    sample.timestamp,
                    sample.elapsed_sec,
                    int(sample.heartbeat_ok),
                    sample.active_clip_index,
                    int(sample.recording_process_alive),
                    sample.cpu_percent,
                    sample.ram_percent,
                    sample.notes,
                ]
            )

    def append_temperature_sample(self) -> None:
        sample = TemperatureSample(
            timestamp=self.now_str(),
            elapsed_sec=int(time.monotonic() - self.start_monotonic),
            internal_temp_c=self.get_temperature_c(),
            outside_temp_f=self.get_outside_temp_f(),
        )
        self.temperature_samples.append(sample)
        with self.temperature_log.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    sample.timestamp,
                    sample.elapsed_sec,
                    sample.internal_temp_c,
                    sample.outside_temp_f,
                ]
            )

    def append_storage_snapshot(self, clip_index: int, output_path: Path, notes: str) -> None:
        clip_exists = output_path.exists()
        clip_size = output_path.stat().st_size if clip_exists else 0
        total_files = list(self.tp08_clips_dir.glob("*"))
        total_count = len([p for p in total_files if p.is_file()])
        total_size = sum(p.stat().st_size for p in total_files if p.is_file())
        with self.storage_log.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    self.now_str(),
                    int(time.monotonic() - self.start_monotonic),
                    clip_index,
                    output_path.name,
                    int(clip_exists),
                    clip_size,
                    total_count,
                    total_size,
                    self.get_disk_used_gb(),
                    self.get_disk_free_gb(),
                    notes,
                ]
            )

    def append_recording_log(self, result: ClipResult) -> None:
        with self.recording_log.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    result.clip_index,
                    result.clip_name,
                    result.format_used,
                    result.start_time,
                    result.end_time,
                    result.intended_duration_sec,
                    result.return_code,
                    int(result.file_exists),
                    int(result.file_nonzero_bytes),
                    result.notes,
                ]
            )

    def get_cpu_percent(self) -> Optional[float]:
        if psutil is None:
            return None
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return None

    def get_ram_percent(self) -> Optional[float]:
        if psutil is None:
            return None
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return None

    def get_disk_used_gb(self) -> float:
        usage = shutil.disk_usage(self.config.evidence_root)
        return round(usage.used / (1024 ** 3), 3)

    def get_disk_free_gb(self) -> float:
        usage = shutil.disk_usage(self.config.evidence_root)
        return round(usage.free / (1024 ** 3), 3)

    def get_outside_temp_f(self) -> Optional[float]:
        if self.config.outside_temp_f is not None:
            return self.config.outside_temp_f
        if self.config.outside_temp_file and self.config.outside_temp_file.exists():
            try:
                text = self.config.outside_temp_file.read_text(encoding="utf-8").strip()
                if text:
                    return float(text.split()[0])
            except Exception:
                pass
        return None

    def get_temperature_c(self) -> Optional[float]:
        thermal_file = Path("/sys/class/thermal/thermal_zone0/temp")
        try:
            if thermal_file.exists():
                return round(int(thermal_file.read_text(encoding="utf-8").strip()) / 1000.0, 2)
        except Exception:
            pass
        vcgencmd = shutil.which("vcgencmd")
        if vcgencmd:
            try:
                result = subprocess.run([vcgencmd, "measure_temp"], capture_output=True, text=True, check=False)
                if result.returncode == 0 and "=" in result.stdout:
                    value = result.stdout.split("=")[1].replace("'C", "").strip()
                    return round(float(value), 2)
            except Exception:
                pass
        return None

    def evaluate_tp08_harness(self) -> Tuple[str, str]:
        actual_elapsed = int(self.end_monotonic - self.start_monotonic)
        if actual_elapsed < self.config.total_record_seconds:
            return (
                "FAIL",
                f"Elapsed runtime {actual_elapsed}s was shorter than configured duration {self.config.total_record_seconds}s",
            )
        if not self.runtime_samples:
            return ("FAIL", "No runtime heartbeat samples were recorded")
        if self.received_stop_signal:
            return ("FAIL", "Run was interrupted by a signal before clean completion")
        if self.failure_messages and len(self.all_clip_results) == 0:
            return ("FAIL", "; ".join(self.failure_messages))
        return (
            "PASS",
            "Harness stayed active for the configured duration with periodic heartbeats",
        )

    def evaluate_tp08_combined(self) -> Tuple[str, str, List[str]]:
        harness_status, harness_reason = self.evaluate_tp08_harness()
        recording_status, recording_reason, _, coverage = evaluate_tp08_recording(
            self.all_clip_results,
            self.config.total_record_seconds,
            self.config.recording_grace_period,
            run_elapsed_sec=int(self.end_monotonic - self.start_monotonic),
        )
        detail = format_recording_coverage_lines(coverage, self.config.recording_grace_period)
        detail.append(f"Harness: {harness_status} — {harness_reason}")
        detail.append(f"Recording: {recording_status} — {recording_reason}")

        if harness_status == "FAIL":
            return "FAIL", harness_reason, detail
        if recording_status == "FAIL":
            return "FAIL", recording_reason, detail
        return (
            "PASS",
            f"{harness_reason}; {recording_reason}",
            detail,
        )

    def evaluate_tp09_heat_run(self) -> Tuple[str, str, List[str]]:
        return evaluate_tp09_heat(
            self.temperature_samples,
            min_avg_outside_f=self.config.tp09_min_avg_outside_temp_f,
            max_internal_c=self.config.tp09_max_internal_temp_c,
            max_avg_internal_c=self.config.tp09_avg_internal_temp_c_limit,
        )

    def write_pass_fail_reports(
        self,
        tp08_status: str,
        tp08_reason: str,
        tp08_detail: List[str],
        tp09_status: str,
        tp09_reason: str,
    ) -> None:
        write_pass_fail(
            self.tp08_pass_fail,
            "TP-08",
            tp08_status,
            tp08_reason,
            [
                "Recording is continuous for at least the configured duration (3 hours in production).",
                "Clip files are present and non-empty.",
                "Harness heartbeats continued for the full run.",
                "System remained operational without early termination.",
            ],
            tp08_detail,
        )
        internal = [s.internal_temp_c for s in self.temperature_samples if s.internal_temp_c is not None]
        outside = [s.outside_temp_f for s in self.temperature_samples if s.outside_temp_f is not None]
        tp09_detail: List[str] = [
            f"Temperature samples: {len(self.temperature_samples)}",
            f"Internal samples with data: {len(internal)}",
            f"Outside samples with data: {len(outside)}",
        ]
        if internal:
            tp09_detail.append(f"Peak internal: {max(internal):.2f} °C (limit {self.config.tp09_max_internal_temp_c} °C)")
            tp09_detail.append(
                f"Average internal: {sum(internal) / len(internal):.2f} °C "
                f"(must be below {self.config.tp09_avg_internal_temp_c_limit} °C)"
            )
        if outside:
            tp09_detail.append(
                f"Average outside: {sum(outside) / len(outside):.1f} °F "
                f"(minimum {self.config.tp09_min_avg_outside_temp_f} °F)"
            )
        write_pass_fail(
            self.tp09_pass_fail,
            "TP-09",
            tp09_status,
            tp09_reason,
            [
                f"Average outside air temperature over the run is {self.config.tp09_min_avg_outside_temp_f} °F or greater.",
                f"Internal Pi temperature never exceeds {self.config.tp09_max_internal_temp_c} °C.",
                f"Average internal Pi temperature is below {self.config.tp09_avg_internal_temp_c_limit} °C.",
            ],
            tp09_detail,
        )


def main(argv: List[str]) -> int:
    if len(argv) > 2:
        print("Usage: python run_endurance_test.py [absolute-path-to-config.json]", file=sys.stderr)
        return 2

    if len(argv) == 2:
        config_path = Path(argv[1]).expanduser()
    else:
        config_path = Path(__file__).resolve().parent / "endurance_config.json"

    try:
        runner = EnduranceRunner(config_path=config_path)
        return runner.run()
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
