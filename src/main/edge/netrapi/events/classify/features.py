"""Stage-1 / stage-2 feature vectors for stop-sign kNN classification."""

from __future__ import annotations

import statistics

from config.types import ApproachConfig
from netrapi.events.approach import ApproachDropEvent, areas_to_percent, prefix_approach_event


RUNTIME_STAGE1_FEATURES = (
    "post_drop_mean_motion",
    "post_drop_min_motion",
    "post_drop_p95_motion",
    "post_drop_stop_fraction",
)

RUNTIME_STAGE2_FEATURES = (
    "post_drop_min_motion",
    "approach_area_sum_pct",
)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def extract_stage1_features(
    motion_samples: list[tuple[float, float]],
    *,
    anchor_s: float,
    window_s: float,
    stopped_threshold: float,
) -> list[float] | None:
    """Return [mean, min, p95, stop_fraction] for [anchor, anchor + window_s] or None."""
    if window_s <= 0:
        return None

    end_s = anchor_s + window_s
    window_scores = [score for time_s, score in motion_samples if anchor_s <= time_s <= end_s]
    if not window_scores:
        return None

    stopped_frames = sum(1 for score in window_scores if score <= stopped_threshold)
    return [
        statistics.fmean(window_scores),
        min(window_scores),
        _percentile(window_scores, 95.0),
        stopped_frames / len(window_scores),
    ]


def compute_approach_area_sum_pct(
    areas: list[float],
    event: ApproachDropEvent,
) -> float | None:
    """Sum of percent areas from approach start through drop end (T₀)."""
    start = event.approach_start_index
    end = event.drop_end_index
    if start < 0 or end < start or end >= len(areas):
        return None

    slice_pct = areas_to_percent(areas[start : end + 1])
    if not slice_pct:
        return None
    return sum(slice_pct)


def extract_stage2_features(
    *,
    stage1_features: list[float],
    areas_snapshot: list[float],
    detect_frame: int,
    fps: float,
    approach_config: ApproachConfig,
) -> list[float] | None:
    """Return [post_drop_min_motion, approach_area_sum_pct] or None."""
    if len(stage1_features) < 2:
        return None
    event = prefix_approach_event(
        areas_snapshot,
        fps,
        detect_frame,
        approach_config=approach_config,
    )
    if event is None:
        return None
    area_sum = compute_approach_area_sum_pct(areas_snapshot, event)
    if area_sum is None:
        return None
    return [stage1_features[1], area_sum]
