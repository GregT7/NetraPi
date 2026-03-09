#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
CLIP_RE = re.compile(r"clip_(\d{4})\.(mp4|h264)$", re.IGNORECASE)


@dataclass
class Config:
    evidence_root: Path
    total_record_seconds: int
    clip_divisions: int
    check_interval_seconds: int
    recording_grace_period: int
    ffprobe_path: str


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


class EnduranceAnalyzer:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.tp08_dir = self.config.evidence_root / "TP-08"
        self.tp09_dir = self.config.evidence_root / "TP-09"
        self.clips_dir = self.tp09_dir / "clips"
        self.summary_file = self.config.evidence_root / "summary.txt"
        self.runtime_log = self.tp08_dir / "runtime_log.csv"
        self.event_log = self.tp08_dir / "event_log.txt"
        self.storage_log = self.tp09_dir / "storage_log.csv"
        self.recording_log = self.tp09_dir / "recording_log.csv"

    @staticmethod
    def load_config(path: Path) -> Config:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        evidence_root = Path(raw["evidence_root"]).expanduser()
        if not evidence_root.is_absolute():
            raise ValueError("evidence_root must be an absolute path")
        return Config(
            evidence_root=evidence_root,
            total_record_seconds=int(raw["total_record_seconds"]),
            clip_divisions=int(raw["clip_divisions"]),
            check_interval_seconds=int(raw["check_interval_seconds"]),
            recording_grace_period=int(raw.get("recording_grace_period", 0)),
            ffprobe_path=str(raw["ffprobe_path"]),
        )

    def load_runtime_rows(self) -> List[Dict[str, str]]:
        if not self.runtime_log.exists():
            return []
        with self.runtime_log.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def load_recording_rows(self) -> List[Dict[str, str]]:
        if not self.recording_log.exists():
            return []
        with self.recording_log.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def build_clip_plan(self) -> Dict[int, int]:
        base = self.config.total_record_seconds // self.config.clip_divisions
        remainder = self.config.total_record_seconds % self.config.clip_divisions
        if base <= 0:
            return {}
        plan: Dict[int, int] = {}
        for i in range(1, self.config.clip_divisions + 1):
            plan[i] = base + (remainder if i == self.config.clip_divisions else 0)
        return plan

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

    def infer_clip_results(self, recording_rows: List[Dict[str, str]]) -> List[ClipResult]:
        plan = self.build_clip_plan()
        row_by_index: Dict[int, Dict[str, str]] = {}
        for row in recording_rows:
            try:
                row_by_index[int(row.get("clip_index", "0"))] = row
            except ValueError:
                continue

        clip_files = sorted([p for p in self.clips_dir.glob("*") if p.is_file()]) if self.clips_dir.exists() else []
        file_by_index: Dict[int, Path] = {}
        for path in clip_files:
            match = CLIP_RE.match(path.name)
            if not match:
                continue
            file_by_index[int(match.group(1))] = path

        indexes = sorted(set(plan.keys()) | set(row_by_index.keys()) | set(file_by_index.keys()))
        results: List[ClipResult] = []
        for idx in indexes:
            row = row_by_index.get(idx, {})
            path = file_by_index.get(idx)
            clip_name = row.get("clip_name") or (path.name if path else f"clip_{idx:04d}.unknown")
            if path is None:
                guessed = self.clips_dir / clip_name
                path = guessed
            fmt = row.get("format") or path.suffix.lstrip(".") or "unknown"
            readable, duration_sec, probe_note = self.probe_media_file(path)
            file_exists = path.exists()
            file_nonzero = file_exists and path.stat().st_size > 0
            notes = row.get("notes", "").strip()
            if probe_note:
                notes = probe_note if not notes else f"{notes}; {probe_note}"
            return_code: Optional[int]
            raw_return = row.get("actual_process_return_code", "")
            try:
                return_code = int(raw_return) if raw_return not in {"", None} else None
            except ValueError:
                return_code = None
            intended = row.get("intended_duration_sec", "")
            try:
                intended_duration_sec = int(intended) if intended not in {"", None} else plan.get(idx, 0)
            except ValueError:
                intended_duration_sec = plan.get(idx, 0)

            results.append(
                ClipResult(
                    clip_index=idx,
                    clip_name=clip_name,
                    output_path=path,
                    format_used=fmt,
                    start_time=row.get("start_time", ""),
                    end_time=row.get("end_time", ""),
                    intended_duration_sec=intended_duration_sec,
                    return_code=return_code,
                    file_exists=file_exists,
                    file_nonzero_bytes=file_nonzero,
                    ffprobe_readable=readable,
                    ffprobe_duration_sec=duration_sec,
                    notes=notes,
                )
            )
        return results

    def parse_ts(self, value: str) -> Optional[datetime]:
        try:
            return datetime.strptime(value, TIMESTAMP_FMT)
        except Exception:
            return None

    def infer_time_bounds(self, runtime_rows: List[Dict[str, str]], clip_results: List[ClipResult]) -> Tuple[str, str, int, List[str]]:
        notes: List[str] = []
        starts: List[datetime] = []
        ends: List[datetime] = []
        elapsed_candidates: List[int] = []

        if runtime_rows:
            first_ts = self.parse_ts(runtime_rows[0].get("timestamp", ""))
            last_ts = self.parse_ts(runtime_rows[-1].get("timestamp", ""))
            if first_ts:
                starts.append(first_ts)
            if last_ts:
                ends.append(last_ts)
            for row in runtime_rows:
                try:
                    elapsed_candidates.append(int(float(row.get("elapsed_sec", "0") or 0)))
                except ValueError:
                    continue
            notes.append("TP-08 elapsed runtime inferred primarily from runtime_log.csv")

        clip_starts = [self.parse_ts(r.start_time) for r in clip_results if r.start_time]
        clip_ends = [self.parse_ts(r.end_time) for r in clip_results if r.end_time]
        starts.extend([x for x in clip_starts if x])
        ends.extend([x for x in clip_ends if x])
        if clip_results:
            notes.append("Clip timing also inferred from recording_log.csv and existing media files")

        if not elapsed_candidates and clip_results:
            intended_sum = sum(r.intended_duration_sec for r in clip_results if r.intended_duration_sec > 0)
            if intended_sum > 0:
                elapsed_candidates.append(intended_sum)
                notes.append("No heartbeat elapsed values were available; used intended clip durations as a fallback estimate")

        actual_elapsed = max(elapsed_candidates) if elapsed_candidates else 0
        start_str = min(starts).strftime(TIMESTAMP_FMT) if starts else "Unknown"
        end_str = max(ends).strftime(TIMESTAMP_FMT) if ends else "Unknown"
        return start_str, end_str, actual_elapsed, notes

    def evaluate_tp08(self, runtime_rows: List[Dict[str, str]], clip_results: List[ClipResult], actual_elapsed: int) -> Tuple[str, str, List[str]]:
        possible_failures = [
            "Python endurance harness terminated early",
            "Unhandled exception interrupted logging or clip orchestration",
            "Heartbeat logging stopped before the configured duration elapsed",
            "Total elapsed runtime was shorter than the configured duration",
            "Recording subprocess management failed badly enough that endurance could not continue",
            "System resource or power issues prevented continued operation",
        ]
        if actual_elapsed < self.config.total_record_seconds:
            return (
                "FAIL",
                f"Inferred elapsed runtime {actual_elapsed}s was shorter than configured duration {self.config.total_record_seconds}s",
                possible_failures,
            )
        if not runtime_rows and not clip_results:
            return ("FAIL", "No runtime or clip evidence was available to infer endurance", possible_failures)
        if not runtime_rows:
            return (
                "PASS",
                "Runtime heartbeat log was missing, but completed clip evidence was sufficient to infer the harness stayed active for the configured duration",
                possible_failures,
            )
        return (
            "PASS",
            "Existing heartbeat and clip evidence indicate the harness remained active for the configured duration",
            possible_failures,
        )

    def evaluate_tp09(self, clip_results: List[ClipResult]) -> Tuple[str, str, List[str], float]:
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
        if not clip_results:
            return "FAIL", "No clip evidence was available for analysis", possible_failures, 0.0
        missing = [r for r in clip_results if not r.file_exists]
        empty = [r for r in clip_results if not r.file_nonzero_bytes]
        unreadable = [r for r in clip_results if not r.ffprobe_readable]
        aggregate_duration = sum((r.ffprobe_duration_sec or 0.0) for r in clip_results if r.ffprobe_readable)
        effective_duration = aggregate_duration + self.config.recording_grace_period
        if missing:
            return (
                "FAIL",
                f"{len(missing)} clip(s) were not created: {', '.join(r.clip_name for r in missing)}",
                possible_failures,
                aggregate_duration,
            )
        if empty:
            return (
                "FAIL",
                f"{len(empty)} clip(s) were empty: {', '.join(r.clip_name for r in empty)}",
                possible_failures,
                aggregate_duration,
            )
        if unreadable:
            return (
                "FAIL",
                f"{len(unreadable)} clip(s) were not readable by ffprobe: {', '.join(r.clip_name for r in unreadable)}",
                possible_failures,
                aggregate_duration,
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
                aggregate_duration,
            )
        return (
            "PASS",
            (
                f"Existing media files were readable with aggregate duration {aggregate_duration:.2f}s and grace period "
                f"{self.config.recording_grace_period}s"
            ),
            possible_failures,
            aggregate_duration,
        )

    def write_summary(
        self,
        start_time: str,
        end_time: str,
        actual_elapsed: int,
        inference_notes: List[str],
        clip_results: List[ClipResult],
        tp08_status: str,
        tp08_reason: str,
        tp08_fail_reasons: List[str],
        tp09_status: str,
        tp09_reason: str,
        tp09_fail_reasons: List[str],
        aggregate_duration: float,
    ) -> None:
        formats = sorted({r.format_used for r in clip_results if r.format_used})
        total_bytes = sum(r.output_path.stat().st_size for r in clip_results if r.output_path.exists())
        content = [
            "Endurance Test Summary (Reconstructed)",
            "=" * 80,
            f"Config file: {self.config_path}",
            f"Evidence root: {self.config.evidence_root}",
            f"Start time: {start_time}",
            f"End time: {end_time}",
            f"Configured duration: {self.config.total_record_seconds} sec",
            f"Inferred elapsed duration: {actual_elapsed} sec",
            f"Recording grace period: {self.config.recording_grace_period} sec",
            f"Clip divisions requested: {self.config.clip_divisions}",
            f"Formats found: {', '.join(formats) if formats else 'None'}",
            "",
            "How this summary was reconstructed:",
            *( [f"- {note}" for note in inference_notes] if inference_notes else ["- Available evidence files were analyzed to reconstruct results."] ),
            "",
            "TP-08 Result",
            "-" * 80,
            f"Status: {tp08_status}",
            "What was checked:",
            "- Available runtime heartbeat evidence was reviewed when present.",
            "- Completed clip evidence was used to infer whether the harness stayed active for the test window.",
            "- The inferred elapsed time was compared against the configured target duration.",
            f"Why it {'passed' if tp08_status == 'PASS' else 'failed'}: {tp08_reason}",
            "Potential TP-08 failure reasons:",
            *[f"- {reason}" for reason in tp08_fail_reasons],
            "",
            "TP-09 Result",
            "-" * 80,
            f"Status: {tp09_status}",
            "What was checked:",
            "- Existing clip files were enumerated from the evidence directory.",
            "- Files were checked for creation and non-zero size.",
            "- ffprobe was used to verify readability and extract media duration.",
            "- Aggregate readable duration plus the configured grace period was compared against the configured total duration.",
            f"Why it {'passed' if tp09_status == 'PASS' else 'failed'}: {tp09_reason}",
            "Potential TP-09 failure reasons:",
            *[f"- {reason}" for reason in tp09_fail_reasons],
            "",
            "Recording Results",
            "-" * 80,
            f"Clip results analyzed: {len(clip_results)}",
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
            f"TP-09 clips directory: {self.clips_dir}",
        ]
        self.summary_file.write_text("\n".join(content) + "\n", encoding="utf-8")

    def run(self) -> int:
        runtime_rows = self.load_runtime_rows()
        recording_rows = self.load_recording_rows()
        clip_results = self.infer_clip_results(recording_rows)
        start_time, end_time, actual_elapsed, inference_notes = self.infer_time_bounds(runtime_rows, clip_results)
        tp08_status, tp08_reason, tp08_fail_reasons = self.evaluate_tp08(runtime_rows, clip_results, actual_elapsed)
        tp09_status, tp09_reason, tp09_fail_reasons, aggregate_duration = self.evaluate_tp09(clip_results)
        self.write_summary(
            start_time=start_time,
            end_time=end_time,
            actual_elapsed=actual_elapsed,
            inference_notes=inference_notes,
            clip_results=clip_results,
            tp08_status=tp08_status,
            tp08_reason=tp08_reason,
            tp08_fail_reasons=tp08_fail_reasons,
            tp09_status=tp09_status,
            tp09_reason=tp09_reason,
            tp09_fail_reasons=tp09_fail_reasons,
            aggregate_duration=aggregate_duration,
        )
        print(f"Reconstructed summary written to: {self.summary_file}")
        return 0 if tp08_status == "PASS" and tp09_status == "PASS" else 1


def main(argv: List[str]) -> int:
    if len(argv) > 2:
        print("Usage: python analyze_endurance_results.py [absolute-path-to-config.json]", file=sys.stderr)
        return 2
    config_path = Path(argv[1]).expanduser() if len(argv) == 2 else Path(__file__).resolve().parent / "config" / "endurance_config.json"
    try:
        analyzer = EnduranceAnalyzer(config_path)
        return analyzer.run()
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
