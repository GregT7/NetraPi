#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import psutil  # type: ignore
except Exception:
    psutil = None


TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
DEFAULT_EVENT_TOTAL = 8


@dataclass
class Config:
    evidence_root: Path
    total_record_seconds: int
    clip_divisions: int
    check_interval_seconds: int
    recording_grace_period: int
    camera_width: int
    camera_height: int
    camera_fps: int
    prefer_mp4: bool
    fallback_to_h264: bool
    preview_enabled: bool
    preview_rotation_degrees: int
    preview_info_enabled: bool
    stop_on_clip_failure: bool
    ffprobe_path: str
    camera_index: int = 0
    extra_rpicam_args: List[str] | None = None


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
    ffprobe_readable: bool
    ffprobe_duration_sec: Optional[float]
    notes: str


@dataclass
class RuntimeSample:
    timestamp: str
    elapsed_sec: int
    heartbeat_ok: bool
    active_clip_index: Optional[int]
    recording_process_alive: bool
    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    disk_used_gb: float
    disk_free_gb: float
    temperature_c: Optional[float]
    notes: str


class EnduranceRunner:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.event_counter = 0
        self.start_monotonic = 0.0
        self.end_monotonic = 0.0
        self.test_start_wall = ""
        self.test_end_wall = ""
        self.active_process: Optional[subprocess.Popen[str]] = None
        self.received_stop_signal = False
        self.all_clip_results: List[ClipResult] = []
        self.runtime_samples: List[RuntimeSample] = []
        self.used_formats: List[str] = []
        self.failure_messages: List[str] = []

        self.tp08_dir = self.config.evidence_root / "TP-08"
        self.tp09_dir = self.config.evidence_root / "TP-09"
        self.tp09_clips_dir = self.tp09_dir / "clips"
        self.summary_file = self.config.evidence_root / "summary.txt"
        self.runtime_log = self.tp08_dir / "runtime_log.csv"
        self.event_log = self.tp08_dir / "event_log.txt"
        self.storage_log = self.tp09_dir / "storage_log.csv"
        self.recording_log = self.tp09_dir / "recording_log.csv"

    @staticmethod
    def load_config(path: Path) -> Config:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        required_keys = [
            "evidence_root",
            "total_record_seconds",
            "clip_divisions",
            "check_interval_seconds",
            "recording_grace_period",
            "camera_width",
            "camera_height",
            "camera_fps",
            "prefer_mp4",
            "fallback_to_h264",
            "preview_enabled",
            "preview_rotation_degrees",
            "preview_info_enabled",
            "stop_on_clip_failure",
            "ffprobe_path",
        ]
        missing = [k for k in required_keys if k not in raw]
        if missing:
            raise ValueError(f"Missing config keys: {', '.join(missing)}")

        evidence_root = Path(raw["evidence_root"]).expanduser()
        if not evidence_root.is_absolute():
            raise ValueError("evidence_root must be an absolute path")

        rotation = int(raw["preview_rotation_degrees"])
        if rotation not in {0, 180}:
            raise ValueError(
                "preview_rotation_degrees must currently be 0 or 180 for rpicam-apps compatibility"
            )

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

        return Config(
            evidence_root=evidence_root,
            total_record_seconds=total_record_seconds,
            clip_divisions=clip_divisions,
            check_interval_seconds=check_interval_seconds,
            recording_grace_period=recording_grace_period,
            camera_width=int(raw["camera_width"]),
            camera_height=int(raw["camera_height"]),
            camera_fps=int(raw["camera_fps"]),
            prefer_mp4=bool(raw["prefer_mp4"]),
            fallback_to_h264=bool(raw["fallback_to_h264"]),
            preview_enabled=bool(raw["preview_enabled"]),
            preview_rotation_degrees=rotation,
            preview_info_enabled=bool(raw["preview_info_enabled"]),
            stop_on_clip_failure=bool(raw["stop_on_clip_failure"]),
            ffprobe_path=str(raw["ffprobe_path"]),
            camera_index=int(raw.get("camera_index", 0)),
            extra_rpicam_args=list(raw.get("extra_rpicam_args", [])),
        )

    def ensure_structure(self) -> None:
        self.config.evidence_root.mkdir(parents=True, exist_ok=True)
        self.tp08_dir.mkdir(parents=True, exist_ok=True)
        self.tp09_dir.mkdir(parents=True, exist_ok=True)
        self.tp09_clips_dir.mkdir(parents=True, exist_ok=True)

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
                    "disk_used_gb",
                    "disk_free_gb",
                    "temperature_c",
                    "notes",
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
                    "ffprobe_readable",
                    "ffprobe_duration_sec",
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
        base = self.config.total_record_seconds // self.config.clip_divisions
        remainder = self.config.total_record_seconds % self.config.clip_divisions
        if base == 0:
            raise ValueError(
                "clip_divisions is too large for total_record_seconds; at least one clip would have 0 seconds"
            )
        plan: List[ClipPlan] = []
        for i in range(1, self.config.clip_divisions + 1):
            duration = base + (remainder if i == self.config.clip_divisions else 0)
            plan.append(ClipPlan(index=i, duration_seconds=duration))
        return plan

    def install_signal_handlers(self) -> None:
        def handler(signum: int, _frame: Any) -> None:
            self.received_stop_signal = True
            self.write_event(f"Received stop signal {signum}; attempting graceful shutdown")
            if self.active_process and self.active_process.poll() is None:
                try:
                    self.active_process.terminate()
                except Exception:
                    pass

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
        tp08_reason = "Summary generation did not complete"
        tp08_fail_reasons: List[str] = []
        tp09_status = "FAIL"
        tp09_reason = "Summary generation did not complete"
        tp09_fail_reasons: List[str] = []

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
                if (
                    not result.file_exists or not result.file_nonzero_bytes or not result.ffprobe_readable
                ) and self.config.stop_on_clip_failure:
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
            tp08_status, tp08_reason, tp08_fail_reasons = self.evaluate_tp08()
            tp09_status, tp09_reason, tp09_fail_reasons = self.evaluate_tp09()
            self.write_event("Post-run verification completed", numbered=True)
            try:
                self.write_summary(
                    tp08_status=tp08_status,
                    tp08_reason=tp08_reason,
                    tp08_fail_reasons=tp08_fail_reasons,
                    tp09_status=tp09_status,
                    tp09_reason=tp09_reason,
                    tp09_fail_reasons=tp09_fail_reasons,
                    plan=plan,
                )
                self.write_event("Summary written", numbered=True)
            except Exception as exc:
                self.write_event(f"Summary write failed: {exc}")
                raise

        return 0 if tp08_status == "PASS" and tp09_status == "PASS" else 1

    def run_single_clip(self, clip: ClipPlan, total_clips: int) -> ClipResult:
        preferred_formats = []
        if self.config.prefer_mp4:
            preferred_formats.append("mp4")
        preferred_formats.append("h264")

        if not self.config.fallback_to_h264:
            preferred_formats = preferred_formats[:1]

        clip_start = self.now_str()
        self.write_event(f"Clip {clip.index}/{total_clips} recording started")

        final_result: Optional[ClipResult] = None
        for fmt in preferred_formats:
            suffix = ".mp4" if fmt == "mp4" else ".h264"
            clip_name = f"clip_{clip.index:04d}{suffix}"
            output_path = self.tp09_clips_dir / clip_name
            command = self.build_record_command(
                output_path=output_path,
                clip_duration_seconds=clip.duration_seconds,
                clip_index=clip.index,
                total_clips=total_clips,
                requested_format=fmt,
            )
            return_code = self.run_recording_subprocess(command, clip.index, output_path)
            exists = output_path.exists()
            nonzero = exists and output_path.stat().st_size > 0
            readable, duration_sec, probe_note = self.probe_media_file(output_path)
            note = probe_note
            if return_code != 0:
                note = self.append_note(note, f"Recorder exited with code {return_code}")
            if fmt == "mp4" and (return_code != 0 or not exists or not nonzero) and self.config.fallback_to_h264:
                note = self.append_note(note, "MP4 attempt failed; trying H264 fallback")
                final_result = ClipResult(
                    clip_index=clip.index,
                    clip_name=clip_name,
                    output_path=output_path,
                    format_used=fmt,
                    start_time=clip_start,
                    end_time=self.now_str(),
                    intended_duration_sec=clip.duration_seconds,
                    return_code=return_code,
                    file_exists=exists,
                    file_nonzero_bytes=nonzero,
                    ffprobe_readable=readable,
                    ffprobe_duration_sec=duration_sec,
                    notes=note,
                )
                continue

            final_result = ClipResult(
                clip_index=clip.index,
                clip_name=clip_name,
                output_path=output_path,
                format_used=fmt,
                start_time=clip_start,
                end_time=self.now_str(),
                intended_duration_sec=clip.duration_seconds,
                return_code=return_code,
                file_exists=exists,
                file_nonzero_bytes=nonzero,
                ffprobe_readable=readable,
                ffprobe_duration_sec=duration_sec,
                notes=note,
            )
            break

        assert final_result is not None
        return final_result

    def build_record_command(
        self,
        output_path: Path,
        clip_duration_seconds: int,
        clip_index: int,
        total_clips: int,
        requested_format: str,
    ) -> List[str]:
        cmd = [
            "rpicam-vid",
            "--camera",
            str(self.config.camera_index),
            "--timeout",
            str(clip_duration_seconds * 1000),
            "--width",
            str(self.config.camera_width),
            "--height",
            str(self.config.camera_height),
            "--framerate",
            str(self.config.camera_fps),
            "--rotation",
            str(self.config.preview_rotation_degrees),
            "--output",
            str(output_path),
        ]

        if not self.config.preview_enabled:
            cmd.append("--nopreview")

        if self.config.preview_info_enabled:
            info_text = (
                f"REC clip {clip_index}/{total_clips} | "
                f"%F %T | {requested_format.upper()} | %fps fps"
            )
            cmd.extend(["--info-text", info_text])

        if requested_format == "h264":
            cmd.extend(["--codec", "h264"])

        if self.config.extra_rpicam_args:
            cmd.extend(self.config.extra_rpicam_args)

        return cmd

    def run_recording_subprocess(
        self,
        command: List[str],
        clip_index: int,
        output_path: Path,
    ) -> int:
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            self.failure_messages.append("rpicam-vid not found in PATH")
            return 127
        except Exception as exc:
            self.failure_messages.append(f"Failed to start rpicam-vid: {exc}")
            return 1

        self.active_process = proc
        next_sample = time.monotonic()
        stderr_tail: List[str] = []

        while proc.poll() is None:
            now = time.monotonic()
            if now >= next_sample:
                self.append_runtime_sample(active_clip_index=clip_index, recording_process_alive=True, notes="heartbeat")
                self.append_storage_snapshot(clip_index, output_path, "heartbeat")
                next_sample = now + self.config.check_interval_seconds
            time.sleep(0.5)
            if self.received_stop_signal:
                break

        _, stderr_data = proc.communicate()
        if stderr_data:
            stderr_tail = stderr_data.strip().splitlines()[-5:]
        if stderr_tail:
            joined = " | ".join(stderr_tail)
            self.write_event(f"Clip {clip_index} recorder stderr tail: {joined}")

        self.active_process = None
        return proc.returncode if proc.returncode is not None else 1

    def append_note(self, existing: str, new_note: str) -> str:
        return new_note if not existing else f"{existing}; {new_note}"

    def probe_media_file(self, path: Path) -> Tuple[bool, Optional[float], str]:
        if not path.exists():
            return False, None, "Output file was not created"
        if path.stat().st_size <= 0:
            return False, None, "Output file is empty"

        ffprobe = shutil.which(self.config.ffprobe_path) or self.config.ffprobe_path
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return False, None, "ffprobe not found"
        except Exception as exc:
            return False, None, f"ffprobe execution failed: {exc}"

        if result.returncode != 0:
            stderr = result.stderr.strip() or "ffprobe returned nonzero exit code"
            return False, None, stderr

        try:
            duration = float(result.stdout.strip())
        except ValueError:
            return False, None, "ffprobe did not return a parseable duration"

        return True, duration, ""

    def append_runtime_sample(self, active_clip_index: Optional[int], recording_process_alive: bool, notes: str) -> None:
        sample = RuntimeSample(
            timestamp=self.now_str(),
            elapsed_sec=int(time.monotonic() - self.start_monotonic),
            heartbeat_ok=True,
            active_clip_index=active_clip_index,
            recording_process_alive=recording_process_alive,
            cpu_percent=self.get_cpu_percent(),
            ram_percent=self.get_ram_percent(),
            disk_used_gb=self.get_disk_used_gb(),
            disk_free_gb=self.get_disk_free_gb(),
            temperature_c=self.get_temperature_c(),
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
                    sample.disk_used_gb,
                    sample.disk_free_gb,
                    sample.temperature_c,
                    sample.notes,
                ]
            )

    def append_storage_snapshot(self, clip_index: int, output_path: Path, notes: str) -> None:
        clip_exists = output_path.exists()
        clip_size = output_path.stat().st_size if clip_exists else 0
        total_files = list(self.tp09_clips_dir.glob("*"))
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
                    int(result.ffprobe_readable),
                    result.ffprobe_duration_sec,
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

    def evaluate_tp08(self) -> Tuple[str, str, List[str]]:
        possible_failures = [
            "Python endurance harness terminated early",
            "Unhandled exception interrupted logging or clip orchestration",
            "Heartbeat logging stopped before the configured duration elapsed",
            "Total elapsed runtime was shorter than the configured duration",
            "Recording subprocess management failed badly enough that endurance could not continue",
            "System resource or power issues prevented continued operation",
        ]

        actual_elapsed = int(self.end_monotonic - self.start_monotonic)
        if actual_elapsed < self.config.total_record_seconds:
            return (
                "FAIL",
                f"Elapsed runtime {actual_elapsed}s was shorter than configured duration {self.config.total_record_seconds}s",
                possible_failures,
            )
        if not self.runtime_samples:
            return (
                "FAIL",
                "No runtime heartbeat samples were recorded",
                possible_failures,
            )
        if self.received_stop_signal:
            return (
                "FAIL",
                "Run was interrupted by a signal before clean completion",
                possible_failures,
            )
        if self.failure_messages and len(self.all_clip_results) == 0:
            return (
                "FAIL",
                "; ".join(self.failure_messages),
                possible_failures,
            )
        return (
            "PASS",
            "Harness stayed active for the configured duration and continued issuing periodic heartbeats while managing clip recordings",
            possible_failures,
        )

    def evaluate_tp09(self) -> Tuple[str, str, List[str]]:
        possible_failures = [
            "Clip file was not created",
            "Clip file was empty",
            "Recorder subprocess returned a nonzero exit code",
            "MP4 output failed and H264 fallback also failed",
            "ffprobe could not read one or more clips",
            "Aggregate readable duration plus grace period was shorter than the configured total duration",
            "Storage exhaustion or write interruption occurred during the run",
            "Camera capture or recording stopped unexpectedly mid-run",
        ]

        if not self.all_clip_results:
            return ("FAIL", "No clip results were recorded", possible_failures)

        unreadable = [r for r in self.all_clip_results if not r.ffprobe_readable]
        missing = [r for r in self.all_clip_results if not r.file_exists]
        empty = [r for r in self.all_clip_results if not r.file_nonzero_bytes]
        aggregate_duration = sum((r.ffprobe_duration_sec or 0.0) for r in self.all_clip_results if r.ffprobe_readable)
        effective_duration = aggregate_duration + self.config.recording_grace_period

        if missing:
            return (
                "FAIL",
                f"{len(missing)} clip(s) were not created: {', '.join(r.clip_name for r in missing)}",
                possible_failures,
            )
        if empty:
            return (
                "FAIL",
                f"{len(empty)} clip(s) were empty: {', '.join(r.clip_name for r in empty)}",
                possible_failures,
            )
        if unreadable:
            return (
                "FAIL",
                f"{len(unreadable)} clip(s) were not readable by ffprobe: {', '.join(r.clip_name for r in unreadable)}",
                possible_failures,
            )
        if effective_duration + 1.0 < self.config.total_record_seconds:
            return (
                "FAIL",
                (
                    f"Aggregate readable duration {aggregate_duration:.2f}s plus grace period "
                    f"{self.config.recording_grace_period}s = {effective_duration:.2f}s, which was shorter "
                    f"than configured duration {self.config.total_record_seconds}s"
                ),
                possible_failures,
            )
        return (
            "PASS",
            (
                f"Segmented recording produced readable retained footage with aggregate duration "
                f"{aggregate_duration:.2f}s and grace period {self.config.recording_grace_period}s"
            ),
            possible_failures,
        )

    def write_summary(
        self,
        tp08_status: str,
        tp08_reason: str,
        tp08_fail_reasons: List[str],
        tp09_status: str,
        tp09_reason: str,
        tp09_fail_reasons: List[str],
        plan: List[ClipPlan],
    ) -> None:
        aggregate_duration = sum((r.ffprobe_duration_sec or 0.0) for r in self.all_clip_results if r.ffprobe_readable)
        clip_duration_list = ", ".join(str(p.duration_seconds) for p in plan)
        total_bytes = sum((r.output_path.stat().st_size if r.output_path.exists() else 0) for r in self.all_clip_results)
        content = [
            "Endurance Test Summary",
            "=" * 80,
            f"Config file: {self.config_path}",
            f"Evidence root: {self.config.evidence_root}",
            f"Start time: {self.test_start_wall}",
            f"End time: {self.test_end_wall}",
            f"Configured duration: {self.config.total_record_seconds} sec",
            f"Actual elapsed duration: {int(self.end_monotonic - self.start_monotonic)} sec",
            f"Recording grace period: {self.config.recording_grace_period} sec",
            f"Clip divisions requested: {self.config.clip_divisions}",
            f"Clip plan (seconds): {clip_duration_list}",
            f"Preview enabled: {self.config.preview_enabled}",
            f"Preview rotation degrees: {self.config.preview_rotation_degrees}",
            f"Preview info enabled: {self.config.preview_info_enabled}",
            f"Formats used: {', '.join(self.used_formats) if self.used_formats else 'None'}",
            "",
            "TP-08 Result",
            "-" * 80,
            f"Status: {tp08_status}",
            "What was checked:",
            "- The endurance harness stayed active for the full configured duration.",
            "- Periodic heartbeats continued throughout the run.",
            "- The harness kept managing sequential clip recordings instead of stopping early.",
            "- The total elapsed time met the target duration.",
            f"Why it {'passed' if tp08_status == 'PASS' else 'failed'}: {tp08_reason}",
            "Potential TP-08 failure reasons:",
            *[f"- {reason}" for reason in tp08_fail_reasons],
            "",
            "TP-09 Result",
            "-" * 80,
            f"Status: {tp09_status}",
            "What was checked:",
            "- Expected clip sequence was attempted for the configured duration.",
            "- Output files were created and checked for non-zero size.",
            "- ffprobe was used to verify media readability when available.",
            "- Aggregate readable duration plus the configured grace period was compared against the configured total duration.",
            f"Why it {'passed' if tp09_status == 'PASS' else 'failed'}: {tp09_reason}",
            "Potential TP-09 failure reasons:",
            *[f"- {reason}" for reason in tp09_fail_reasons],
            "",
            "Recording Results",
            "-" * 80,
            f"Clip results recorded: {len(self.all_clip_results)}",
            f"Aggregate readable duration: {aggregate_duration:.2f} sec",
            f"Aggregate readable duration + grace: {aggregate_duration + self.config.recording_grace_period:.2f} sec",
            f"Total stored bytes: {total_bytes}",
            "",
            "Evidence File Locations",
            "-" * 80,
            f"TP-08 runtime log: {self.runtime_log}",
            f"TP-08 event log: {self.event_log}",
            f"TP-09 storage log: {self.storage_log}",
            f"TP-09 recording log: {self.recording_log}",
            f"TP-09 clips directory: {self.tp09_clips_dir}",
        ]
        self.summary_file.write_text("\n".join(content) + "\n", encoding="utf-8")


def main(argv: List[str]) -> int:
    if len(argv) > 2:
        print("Usage: python run_endurance_test.py [absolute-path-to-config.json]", file=sys.stderr)
        return 2

    if len(argv) == 2:
        config_path = Path(argv[1]).expanduser()
    else:
        config_path = Path(__file__).resolve().parent / "config" / "endurance_config.json"

    try:
        runner = EnduranceRunner(config_path=config_path)
        return runner.run()
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
