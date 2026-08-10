"""Shared approach → motion window → two-stage kNN cycle logic for AT-3.4."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

STAGE1_FEATURE_NAMES: tuple[str, ...] = (
    "post_drop_mean_motion",
    "post_drop_min_motion",
    "post_drop_p95_motion",
    "post_drop_stop_fraction",
)

STAGE2_FEATURE_NAMES: tuple[str, ...] = (
    "post_drop_min_motion",
    "approach_area_sum_pct",
)

DEFAULT_DETECTOR_SCORE_THRESHOLD = 0.35
DEFAULT_MIN_BOX_CENTER_X = 0.5

UNSAFE_SUBTYPE_LABELS = ("rolling-stop", "run-through")


@dataclass
class ApproachCycle:
    t0_s: float
    detect_frame: int
    areas_snapshot: list[float]
    area_at_detect: float
    motion_samples: list[tuple[float, float]] = field(default_factory=list)
    motion_raw: list[float] = field(default_factory=list)
    classified: bool = False
    classify_at_s: float | None = None
    stage1_predicted: str = ""
    stage2_predicted: str = ""
    e2e_predicted: str = ""
    stage1_features: list[float] = field(default_factory=list)
    stage2_features: list[float] = field(default_factory=list)
    banners_clear_at_s: float | None = None


def e2e_predicted(stage1_predicted: str, stage2_predicted: str) -> str:
    if stage1_predicted == "complete-stop":
        return "complete-stop"
    if stage1_predicted == "rolling-or-run-through":
        if stage2_predicted in UNSAFE_SUBTYPE_LABELS:
            return stage2_predicted
        return "rolling-or-run-through"
    return ""


def safety_label(stage1_predicted: str) -> str:
    if stage1_predicted == "complete-stop":
        return "safe"
    if stage1_predicted == "rolling-or-run-through":
        return "unsafe"
    return ""


def max_stop_sign_area_fraction(
    *,
    boxes: np.ndarray,
    classes: np.ndarray,
    scores: np.ndarray,
    count: int,
    labels: dict[int, str],
    stop_sign_label: str = "stop sign",
    score_threshold: float = DEFAULT_DETECTOR_SCORE_THRESHOLD,
    min_box_center_x: float = DEFAULT_MIN_BOX_CENTER_X,
) -> float:
    best = 0.0
    limit = min(count, len(scores))
    for index in range(limit):
        score = float(scores[index])
        if score < score_threshold:
            continue
        class_id = int(classes[index])
        label = labels.get(class_id, "").strip().lower()
        if label != stop_sign_label:
            continue
        ymin, xmin, ymax, xmax = boxes[index]
        x_center = (float(xmin) + float(xmax)) / 2.0
        if x_center < min_box_center_x:
            continue
        width = max(0.0, float(xmax) - float(xmin))
        height = max(0.0, float(ymax) - float(ymin))
        best = max(best, width * height)
    return best


def arm_approach_cycle(
    *,
    elapsed_s: float,
    area_series: list[float],
    area_fraction: float,
) -> ApproachCycle:
    """Snapshot prefix areas for stage-2, then clear live series so the pattern cannot re-fire.

    Does not reset the motion tracker: idle ``prime_gray`` must keep ``_prev_gray`` so the
    first post-T0 ``score()`` is a real optical-flow comparison (not a bootstrap 0.0).
    """
    detect_frame = len(area_series) - 1
    cycle = ApproachCycle(
        t0_s=elapsed_s,
        detect_frame=detect_frame,
        areas_snapshot=list(area_series),
        area_at_detect=area_fraction,
    )
    area_series.clear()
    return cycle


def lock_cycle_buffers(*, area_series: list[float], motion_tracker: Any) -> None:
    area_series.clear()
    motion_tracker.reset()


def classify_approach_cycle(
    cycle: ApproachCycle,
    *,
    approach_config,
    motion_config,
    post_drop_window_s: float,
    stage1_pipeline,
    stage2_pipeline,
    fps: float,
) -> dict[str, Any] | None:
    from approach_phase_metrics import compute_approach_phase_metrics
    from knn_feature_registry import prefix_approach_event
    from runtime_motion_features import extract_runtime_knn_features

    stage1_features = extract_runtime_knn_features(
        cycle.motion_samples,
        anchor_s=cycle.t0_s,
        window_s=post_drop_window_s,
        stopped_threshold=motion_config.stopped_motion_threshold,
    )
    if stage1_features is None:
        return None

    event = prefix_approach_event(
        cycle.areas_snapshot,
        fps,
        cycle.detect_frame,
        approach_config=approach_config,
    )
    if event is None:
        return None

    _duration, approach_area_sum_pct, _mean = compute_approach_phase_metrics(
        cycle.areas_snapshot,
        event,
    )
    if approach_area_sum_pct is None:
        return None

    stage2_features = [stage1_features[1], approach_area_sum_pct]

    stage1_predicted = str(stage1_pipeline.predict([stage1_features])[0])
    stage2_predicted = ""
    if stage1_predicted == "rolling-or-run-through" and stage2_pipeline is not None:
        stage2_predicted = str(stage2_pipeline.predict([stage2_features])[0])
    e2e = e2e_predicted(stage1_predicted, stage2_predicted)

    return {
        "stage1_features": stage1_features,
        "stage2_features": stage2_features,
        "stage1_predicted": stage1_predicted,
        "stage2_predicted": stage2_predicted,
        "e2e_predicted": e2e,
    }
