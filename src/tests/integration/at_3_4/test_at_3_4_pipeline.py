"""Unit tests for AT-3.4 shared pipeline helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

AT_3_4_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AT_3_4_DIR))

from at_3_4_pipeline import (  # noqa: E402
    arm_approach_cycle,
    e2e_predicted,
    lock_cycle_buffers,
    max_stop_sign_area_fraction,
)


class _FakeMotionTracker:
    def __init__(self) -> None:
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1


def test_e2e_predicted_complete_stop() -> None:
    assert e2e_predicted("complete-stop", "") == "complete-stop"


def test_e2e_predicted_unsafe_subtype() -> None:
    assert e2e_predicted("rolling-or-run-through", "rolling-stop") == "rolling-stop"
    assert e2e_predicted("rolling-or-run-through", "run-through") == "run-through"


def test_arm_approach_cycle_clears_area_series() -> None:
    area_series = [0.0, 0.001, 0.002, 0.003]
    cycle = arm_approach_cycle(
        elapsed_s=1.5,
        area_series=area_series,
        area_fraction=0.003,
    )
    assert cycle.detect_frame == 3
    assert cycle.areas_snapshot == [0.0, 0.001, 0.002, 0.003]
    assert area_series == []


def test_lock_cycle_buffers() -> None:
    area_series = [0.1, 0.2]
    tracker = _FakeMotionTracker()
    lock_cycle_buffers(area_series=area_series, motion_tracker=tracker)
    assert area_series == []
    assert tracker.reset_count == 1


def test_max_stop_sign_area_fraction_filters_left_sign() -> None:
    boxes = np.array([[0.1, 0.1, 0.2, 0.2]], dtype=np.float32)
    classes = np.array([1], dtype=np.int32)
    scores = np.array([0.9], dtype=np.float32)
    labels = {1: "stop sign"}
    area = max_stop_sign_area_fraction(
        boxes=boxes,
        classes=classes,
        scores=scores,
        count=1,
        labels=labels,
        score_threshold=0.35,
        min_box_center_x=0.5,
    )
    assert area == 0.0

    boxes_right = np.array([[0.1, 0.6, 0.2, 0.8]], dtype=np.float32)
    area_right = max_stop_sign_area_fraction(
        boxes=boxes_right,
        classes=classes,
        scores=scores,
        count=1,
        labels=labels,
        score_threshold=0.35,
        min_box_center_x=0.5,
    )
    assert area_right == pytest.approx(0.02)
