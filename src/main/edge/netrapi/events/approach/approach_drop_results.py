from __future__ import annotations

from dataclasses import dataclass

from config.types import ApproachConfig


@dataclass(frozen=True)
class ApproachDropEvent:
    peak_index: int
    peak_time_s: float
    peak_area_pct: float
    approach_start_index: int
    approach_start_time_s: float
    approach_start_area_pct: float
    drop_end_index: int
    drop_end_time_s: float
    drop_end_area_pct: float
    approach_duration_s: float
    drop_duration_s: float
    log_linear_r2: float
    increasing_fraction: float
    score: float


@dataclass(frozen=True)
class PeakCandidateDiagnosis:
    peak_index: int
    peak_time_s: float
    peak_area_pct: float
    approach_start_index: int | None
    approach_start_time_s: float | None
    approach_start_area_pct: float | None
    approach_duration_s: float | None
    increasing_fraction: float | None
    log_linear_r2: float | None
    drop_end_index: int | None
    drop_end_time_s: float | None
    drop_end_area_pct: float | None
    drop_duration_s: float | None
    post_drop_holds: bool | None
    fail_reasons: tuple[str, ...]
    passed: bool
    score: float | None


@dataclass(frozen=True)
class ApproachDropDiagnosis:
    event: ApproachDropEvent | None
    frame_count: int
    fps: float
    global_max_index: int
    global_max_time_s: float
    global_max_area_pct: float
    peak_candidates: tuple[PeakCandidateDiagnosis, ...]
    config: ApproachConfig
