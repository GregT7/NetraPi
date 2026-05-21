#!/usr/bin/env python3
"""Reconstruct TP-08 / TP-09 pass/fail from evidence on disk (same rules as run_endurance_test.py)."""
from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from run_endurance_test import (
    ClipResult,
    TemperatureSample,
    build_clip_duration_plan,
    evaluate_tp08_recording,
    evaluate_tp09_heat,
    format_recording_coverage_lines,
    write_pass_fail,
)

CLIP_RE = re.compile(r"clip_(\d{4})\.mp4$", re.IGNORECASE)


@dataclass
class AnalysisConfig:
    evidence_root: Path
    total_record_seconds: int
    clip_divisions: int
    recording_grace_period: int
    tp09_max_internal_temp_c: float
    tp09_avg_internal_temp_c_limit: float
    tp09_min_avg_outside_temp_f: float


def load_analysis_config(path: Path) -> AnalysisConfig:
    with path.open("r", encoding="utf-8-sig") as f:
        raw = json.load(f)
    required = [
        "evidence_root",
        "total_record_seconds",
        "clip_divisions",
        "recording_grace_period",
    ]
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")
    evidence_root = Path(raw["evidence_root"]).expanduser()
    if not evidence_root.is_absolute():
        raise ValueError("evidence_root must be an absolute path")
    from run_endurance_test import (
        TP09_AVG_INTERNAL_TEMP_C_LIMIT,
        TP09_MAX_INTERNAL_TEMP_C,
        TP09_MIN_AVG_OUTSIDE_TEMP_F,
    )

    return AnalysisConfig(
        evidence_root=evidence_root,
        total_record_seconds=int(raw["total_record_seconds"]),
        clip_divisions=int(raw["clip_divisions"]),
        recording_grace_period=int(raw.get("recording_grace_period", 0)),
        tp09_max_internal_temp_c=float(raw.get("tp09_max_internal_temp_c", TP09_MAX_INTERNAL_TEMP_C)),
        tp09_avg_internal_temp_c_limit=float(
            raw.get("tp09_avg_internal_temp_c_limit", TP09_AVG_INTERNAL_TEMP_C_LIMIT)
        ),
        tp09_min_avg_outside_temp_f=float(
            raw.get("tp09_min_avg_outside_temp_f", TP09_MIN_AVG_OUTSIDE_TEMP_F)
        ),
    )


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _parse_optional_float(value: str) -> Optional[float]:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_temperature_samples(path: Path) -> List[TemperatureSample]:
    rows = load_csv_rows(path)
    samples: List[TemperatureSample] = []
    for row in rows:
        try:
            elapsed = int(float(row.get("elapsed_sec", "0") or 0))
        except ValueError:
            elapsed = 0
        samples.append(
            TemperatureSample(
                timestamp=row.get("timestamp", ""),
                elapsed_sec=elapsed,
                internal_temp_c=_parse_optional_float(row.get("internal_temp_c", "")),
                outside_temp_f=_parse_optional_float(row.get("outside_temp_f", "")),
            )
        )
    return samples


def infer_clip_results(
    config: AnalysisConfig,
    recording_rows: List[Dict[str, str]],
) -> List[ClipResult]:
    plan = build_clip_duration_plan(config.total_record_seconds, config.clip_divisions)
    if not plan:
        return []

    tp08_dir = config.evidence_root / "TP-08"
    clips_dir = tp08_dir / "clips"
    legacy_clips_dir = config.evidence_root / "TP-09" / "clips"
    if not clips_dir.exists() and legacy_clips_dir.exists():
        clips_dir = legacy_clips_dir

    row_by_index: Dict[int, Dict[str, str]] = {}
    for row in recording_rows:
        try:
            row_by_index[int(row.get("clip_index", "0"))] = row
        except ValueError:
            continue

    clip_files = sorted([p for p in clips_dir.glob("*") if p.is_file()]) if clips_dir.exists() else []
    file_by_index: Dict[int, Path] = {}
    for clip_path in clip_files:
        match = CLIP_RE.match(clip_path.name)
        if not match:
            continue
        file_by_index[int(match.group(1))] = clip_path

    indexes = sorted(set(plan.keys()) | set(row_by_index.keys()) | set(file_by_index.keys()))
    results: List[ClipResult] = []
    for idx in indexes:
        row = row_by_index.get(idx, {})
        path = file_by_index.get(idx)
        clip_name = row.get("clip_name") or (path.name if path else f"clip_{idx:04d}.mp4")
        if path is None:
            path = clips_dir / clip_name
        fmt = row.get("format") or path.suffix.lstrip(".") or "unknown"
        notes = row.get("notes", "").strip()
        if path.exists():
            file_exists = True
            file_nonzero = path.stat().st_size > 0
        else:
            file_exists = row.get("file_exists", "") == "1"
            file_nonzero = row.get("file_nonzero_bytes", "") == "1"
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
                notes=notes,
            )
        )
    return results


def infer_time_bounds(
    runtime_rows: List[Dict[str, str]],
    clip_results: List[ClipResult],
) -> int:
    elapsed_candidates: List[int] = []
    if runtime_rows:
        for row in runtime_rows:
            try:
                elapsed_candidates.append(int(float(row.get("elapsed_sec", "0") or 0)))
            except ValueError:
                continue
    if not elapsed_candidates and clip_results:
        intended_sum = sum(r.intended_duration_sec for r in clip_results if r.intended_duration_sec > 0)
        if intended_sum > 0:
            elapsed_candidates.append(intended_sum)
    return max(elapsed_candidates) if elapsed_candidates else 0


def evaluate_tp08_reconstructed(
    runtime_rows: List[Dict[str, str]],
    clip_results: List[ClipResult],
    actual_elapsed: int,
    config: AnalysisConfig,
) -> Tuple[str, str, List[str]]:
    harness_reason = ""
    if actual_elapsed < config.total_record_seconds:
        harness_status = "FAIL"
        harness_reason = (
            f"Inferred elapsed runtime {actual_elapsed}s was shorter than configured duration "
            f"{config.total_record_seconds}s"
        )
    elif not runtime_rows and not clip_results:
        harness_status = "FAIL"
        harness_reason = "No runtime or clip evidence was available to infer endurance"
    elif not runtime_rows:
        harness_status = "PASS"
        harness_reason = (
            "Runtime heartbeat log was missing, but clip evidence supports the configured duration"
        )
    else:
        harness_status = "PASS"
        harness_reason = "Heartbeat and clip evidence indicate the harness remained active for the configured duration"

    recording_status, recording_reason, _, coverage = evaluate_tp08_recording(
        clip_results,
        config.total_record_seconds,
        config.recording_grace_period,
        run_elapsed_sec=actual_elapsed,
    )
    detail = format_recording_coverage_lines(coverage, config.recording_grace_period)
    detail.append(f"Harness: {harness_status} — {harness_reason}")
    detail.append(f"Recording: {recording_status} — {recording_reason}")

    if harness_status == "FAIL":
        return "FAIL", harness_reason, detail
    if recording_status == "FAIL":
        return "FAIL", recording_reason, detail
    return "PASS", f"{harness_reason}; {recording_reason}", detail


def run_analysis(config_path: Path) -> int:
    config = load_analysis_config(config_path)
    tp08_dir = config.evidence_root / "TP-08"
    tp09_dir = config.evidence_root / "TP-09"

    runtime_log = tp08_dir / "runtime_log.csv"
    recording_log = tp08_dir / "recording_log.csv"
    if not recording_log.exists():
        legacy = tp09_dir / "recording_log.csv"
        if legacy.exists():
            recording_log = legacy

    temperature_log = tp09_dir / "temperature_log.csv"

    runtime_rows = load_csv_rows(runtime_log)
    recording_rows = load_csv_rows(recording_log)
    clip_results = infer_clip_results(config, recording_rows)
    actual_elapsed = infer_time_bounds(runtime_rows, clip_results)
    temperature_samples = load_temperature_samples(temperature_log)

    tp08_status, tp08_reason, tp08_detail = evaluate_tp08_reconstructed(
        runtime_rows, clip_results, actual_elapsed, config
    )
    tp09_status, tp09_reason, _ = evaluate_tp09_heat(
        temperature_samples,
        min_avg_outside_f=config.tp09_min_avg_outside_temp_f,
        max_internal_c=config.tp09_max_internal_temp_c,
        max_avg_internal_c=config.tp09_avg_internal_temp_c_limit,
    )

    tp08_pass_fail = tp08_dir / "pass_fail.txt"
    tp09_pass_fail = tp09_dir / "pass_fail.txt"
    tp08_dir.mkdir(parents=True, exist_ok=True)
    tp09_dir.mkdir(parents=True, exist_ok=True)

    write_pass_fail(
        tp08_pass_fail,
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

    internal = [s.internal_temp_c for s in temperature_samples if s.internal_temp_c is not None]
    outside = [s.outside_temp_f for s in temperature_samples if s.outside_temp_f is not None]
    tp09_detail: List[str] = [
        f"Temperature samples: {len(temperature_samples)}",
        f"Internal samples with data: {len(internal)}",
        f"Outside samples with data: {len(outside)}",
    ]
    if internal:
        tp09_detail.append(f"Peak internal: {max(internal):.2f} °C (limit {config.tp09_max_internal_temp_c} °C)")
        tp09_detail.append(
            f"Average internal: {sum(internal) / len(internal):.2f} °C "
            f"(must be below {config.tp09_avg_internal_temp_c_limit} °C)"
        )
    if outside:
        tp09_detail.append(
            f"Average outside: {sum(outside) / len(outside):.1f} °F "
            f"(minimum {config.tp09_min_avg_outside_temp_f} °F)"
        )

    write_pass_fail(
        tp09_pass_fail,
        "TP-09",
        tp09_status,
        tp09_reason,
        [
            f"Average outside air temperature over the run is {config.tp09_min_avg_outside_temp_f} °F or greater.",
            f"Internal Pi temperature never exceeds {config.tp09_max_internal_temp_c} °C.",
            f"Average internal Pi temperature is below {config.tp09_avg_internal_temp_c_limit} °C.",
        ],
        tp09_detail,
    )

    print(f"TP-08 pass/fail written to: {tp08_pass_fail} ({tp08_status})")
    print(f"TP-09 pass/fail written to: {tp09_pass_fail} ({tp09_status})")
    return 0 if tp08_status == "PASS" and tp09_status == "PASS" else 1


def main(argv: List[str]) -> int:
    if len(argv) > 2:
        print("Usage: python analyze_endurance_results.py [absolute-path-to-config.json]", file=sys.stderr)
        return 2
    config_path = Path(argv[1]).expanduser() if len(argv) == 2 else Path(__file__).resolve().parent / "endurance_config.json"
    try:
        return run_analysis(config_path)
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
