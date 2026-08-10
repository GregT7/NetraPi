"""Detect stop-sign approach pattern: exponential area growth then sharp drop after peak."""

from __future__ import annotations

import math

from config.types import ApproachConfig
from netrapi.events.approach.approach_drop_results import (
    ApproachDropDiagnosis,
    ApproachDropEvent,
    PeakCandidateDiagnosis,
)


def areas_to_percent(areas: list[float]) -> list[float]:
    return [value * 100.0 for value in areas]


def _log_linear_r2(times: list[float], values_pct: list[float], start: int, end: int) -> float:
    xs: list[float] = []
    ys: list[float] = []
    for index in range(start, end + 1):
        value = values_pct[index]
        if value > 1e-6:
            xs.append(times[index])
            ys.append(math.log(value))

    count = len(xs)
    if count < 4:
        return 0.0

    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x <= 0:
        return 0.0

    cov_xy = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(count))
    slope = cov_xy / var_x
    intercept = mean_y - slope * mean_x

    ss_res = sum((ys[i] - (slope * xs[i] + intercept)) ** 2 for i in range(count))
    ss_tot = sum((ys[i] - mean_y) ** 2 for i in range(count))
    if ss_tot <= 0:
        return 0.0
    return max(0.0, 1.0 - ss_res / ss_tot)


def _increasing_fraction(
    values_pct: list[float],
    start: int,
    end: int,
    *,
    stride: int = 1,
) -> float:
    if end <= start or stride < 1:
        return 0.0
    steps = 0
    rising = 0
    for index in range(start + stride, end + 1, stride):
        steps += 1
        if values_pct[index] > values_pct[index - stride]:
            rising += 1
    return rising / steps if steps else 0.0


def _peak_candidates(values_pct: list[float], *, min_peak_pct: float) -> list[int]:
    if not values_pct:
        return []

    candidates: list[int] = []
    last_index = len(values_pct) - 1
    for index in range(1, last_index):
        value = values_pct[index]
        if value < min_peak_pct:
            continue
        if value > values_pct[index - 1] and value >= values_pct[index + 1]:
            candidates.append(index)

    global_index = max(range(len(values_pct)), key=values_pct.__getitem__)
    if values_pct[global_index] >= min_peak_pct and global_index not in candidates:
        candidates.append(global_index)

    return sorted(candidates, key=lambda idx: values_pct[idx], reverse=True)


def _approach_start_index(
    values_pct: list[float],
    peak_index: int,
    peak_value: float,
    *,
    start_ratio: float,
) -> int:
    threshold = peak_value * start_ratio
    index = peak_index
    while index > 0:
        index -= 1
        if values_pct[index] <= threshold:
            return index + 1
    return 0


def _drop_end_index(
    values_pct: list[float],
    peak_index: int,
    peak_value: float,
    *,
    drop_ratio: float,
    max_index: int,
) -> int | None:
    threshold = peak_value * drop_ratio
    limit = min(len(values_pct) - 1, max_index)
    for index in range(peak_index + 1, limit + 1):
        if values_pct[index] <= threshold:
            return index
    return None


def _post_drop_holds(
    values_pct: list[float],
    drop_end_index: int,
    peak_value: float,
    fps: float,
    *,
    hold_s: float,
    peak_ratio: float,
) -> bool:
    hold_frames = max(1, int(hold_s * fps))
    threshold = peak_value * peak_ratio
    end = min(len(values_pct), drop_end_index + hold_frames)
    if end <= drop_end_index:
        return False
    return all(values_pct[index] <= threshold for index in range(drop_end_index, end))


def _score_event(
    *,
    peak_area_pct: float,
    log_r2: float,
    increasing_fraction: float,
    approach_duration_s: float,
    drop_duration_s: float,
    config: ApproachConfig,
) -> float:
    peak_term = min(1.0, peak_area_pct / 3.0)
    approach_term = min(1.0, approach_duration_s / 4.0)
    drop_term = max(0.0, 1.0 - drop_duration_s / config.drop_within_s)
    return (
        0.30 * log_r2
        + 0.20 * increasing_fraction
        + 0.20 * peak_term
        + 0.15 * approach_term
        + 0.15 * drop_term
    )


def _diagnose_peak_candidate(
    *,
    peak_index: int,
    values_pct: list[float],
    times: list[float],
    fps: float,
    config: ApproachConfig,
    max_drop_frames: int,
    min_approach_frames: int,
    max_approach_frames: int,
    rising_stride: int,
) -> PeakCandidateDiagnosis:
    peak_value = values_pct[peak_index]
    fail_reasons: list[str] = []

    approach_start = _approach_start_index(
        values_pct,
        peak_index,
        peak_value,
        start_ratio=config.approach_start_peak_ratio,
    )
    approach_frames = peak_index - approach_start
    approach_duration_s = approach_frames / fps
    approach_start_time_s = times[approach_start]
    approach_start_area_pct = values_pct[approach_start]

    if approach_frames < min_approach_frames:
        fail_reasons.append("approach_too_short")
    elif approach_frames > max_approach_frames:
        fail_reasons.append("approach_too_long")

    increasing_fraction = _increasing_fraction(
        values_pct,
        approach_start,
        peak_index,
        stride=rising_stride,
    )
    if increasing_fraction < config.min_increasing_fraction:
        fail_reasons.append("rising_fraction")

    log_r2 = _log_linear_r2(times, values_pct, approach_start, peak_index)
    if log_r2 < config.min_log_linear_r2:
        fail_reasons.append("log_r2")

    drop_end = _drop_end_index(
        values_pct,
        peak_index,
        peak_value,
        drop_ratio=config.drop_to_peak_ratio,
        max_index=peak_index + max_drop_frames,
    )
    drop_duration_s: float | None = None
    post_drop_holds: bool | None = None
    if drop_end is None:
        fail_reasons.append("drop")
    else:
        drop_duration_s = (drop_end - peak_index) / fps
        post_drop_holds = _post_drop_holds(
            values_pct,
            drop_end,
            peak_value,
            fps,
            hold_s=config.post_drop_hold_s,
            peak_ratio=config.post_drop_peak_ratio,
        )
        if not post_drop_holds:
            fail_reasons.append("post_drop_hold")

    passed = not fail_reasons
    score: float | None = None
    if increasing_fraction is not None and log_r2 is not None and drop_duration_s is not None:
        score = _score_event(
            peak_area_pct=peak_value,
            log_r2=log_r2,
            increasing_fraction=increasing_fraction,
            approach_duration_s=approach_duration_s,
            drop_duration_s=drop_duration_s,
            config=config,
        )

    return PeakCandidateDiagnosis(
        peak_index=peak_index,
        peak_time_s=times[peak_index],
        peak_area_pct=peak_value,
        approach_start_index=approach_start,
        approach_start_time_s=approach_start_time_s,
        approach_start_area_pct=approach_start_area_pct,
        approach_duration_s=approach_duration_s,
        increasing_fraction=increasing_fraction,
        log_linear_r2=log_r2,
        drop_end_index=drop_end,
        drop_end_time_s=times[drop_end] if drop_end is not None else None,
        drop_end_area_pct=values_pct[drop_end] if drop_end is not None else None,
        drop_duration_s=drop_duration_s,
        post_drop_holds=post_drop_holds,
        fail_reasons=tuple(fail_reasons),
        passed=passed,
        score=score,
    )


def _run_approach_diagnosis(
    areas: list[float],
    fps: float,
    config: ApproachConfig,
) -> ApproachDropDiagnosis:
    values_pct = areas_to_percent(areas)
    times = [index / fps for index in range(len(values_pct))]
    max_drop_frames = max(1, int(config.drop_within_s * fps))
    min_approach_frames = max(2, int(config.min_approach_s * fps))
    max_approach_frames = max(min_approach_frames, int(config.max_approach_s * fps))
    rising_stride = max(1, int(round(fps / 10)))

    global_max_index = max(range(len(values_pct)), key=values_pct.__getitem__)
    peak_candidates: list[PeakCandidateDiagnosis] = []
    best_event: ApproachDropEvent | None = None

    for peak_index in _peak_candidates(values_pct, min_peak_pct=config.min_peak_pct):
        diagnosis = _diagnose_peak_candidate(
            peak_index=peak_index,
            values_pct=values_pct,
            times=times,
            fps=fps,
            config=config,
            max_drop_frames=max_drop_frames,
            min_approach_frames=min_approach_frames,
            max_approach_frames=max_approach_frames,
            rising_stride=rising_stride,
        )
        peak_candidates.append(diagnosis)
        if not diagnosis.passed:
            continue

        event = ApproachDropEvent(
            peak_index=diagnosis.peak_index,
            peak_time_s=diagnosis.peak_time_s,
            peak_area_pct=diagnosis.peak_area_pct,
            approach_start_index=diagnosis.approach_start_index or diagnosis.peak_index,
            approach_start_time_s=diagnosis.approach_start_time_s or 0.0,
            approach_start_area_pct=diagnosis.approach_start_area_pct or 0.0,
            drop_end_index=diagnosis.drop_end_index or diagnosis.peak_index,
            drop_end_time_s=diagnosis.drop_end_time_s or diagnosis.peak_time_s,
            drop_end_area_pct=diagnosis.drop_end_area_pct or 0.0,
            approach_duration_s=diagnosis.approach_duration_s or 0.0,
            drop_duration_s=diagnosis.drop_duration_s or 0.0,
            log_linear_r2=diagnosis.log_linear_r2 or 0.0,
            increasing_fraction=diagnosis.increasing_fraction or 0.0,
            score=diagnosis.score or 0.0,
        )
        if best_event is None or event.score > best_event.score:
            best_event = event

    return ApproachDropDiagnosis(
        event=best_event,
        frame_count=len(values_pct),
        fps=fps,
        global_max_index=global_max_index,
        global_max_time_s=times[global_max_index],
        global_max_area_pct=values_pct[global_max_index],
        peak_candidates=tuple(peak_candidates),
        config=config,
    )


def diagnose_approach_drop(
    areas: list[float],
    fps: float,
    *,
    config: ApproachConfig | None = None,
) -> ApproachDropDiagnosis | None:
    """Return detection result plus per-peak metrics for logging and tuning."""
    if not areas or fps <= 0:
        return None

    if config is None:
        raise ValueError("ApproachConfig is required")
    return _run_approach_diagnosis(areas, fps, config)


def prefix_approach_event(
    areas: list[float],
    fps: float,
    detect_frame: int,
    *,
    approach_config: ApproachConfig,
) -> ApproachDropEvent | None:
    """Approach event on the per-frame detection prefix through detect_frame."""
    if detect_frame < 0 or detect_frame >= len(areas):
        return None
    diagnosis = diagnose_approach_drop(
        areas[: detect_frame + 1],
        fps,
        config=approach_config,
    )
    if diagnosis is None or diagnosis.event is None:
        return None
    return diagnosis.event
