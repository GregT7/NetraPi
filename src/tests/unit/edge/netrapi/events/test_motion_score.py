from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from config.loader import AppConfig
from netrapi.events.classify.motion_score import LiveMotionTracker, prepare_gray, raw_flow_score

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "config"


def _motion_config():
    return AppConfig.load(FIXTURES_DIR).motion


def test_prepare_gray_scales_and_converts():
    frame = np.zeros((40, 80, 3), dtype=np.uint8)
    frame[:, :] = (10, 20, 30)
    gray = prepare_gray(frame, flow_scale=0.5)

    assert gray.ndim == 2
    assert gray.shape[0] == 20
    assert gray.shape[1] == 40


def test_live_motion_tracker_first_score_is_zero_then_positive_on_shift():
    config = _motion_config()
    tracker = LiveMotionTracker(config)

    base = np.zeros((48, 64, 3), dtype=np.uint8)
    shifted = base.copy()
    shifted[30:45, 20:44] = 255

    tracker.prime(base)
    first = tracker.score(base)
    assert first == pytest.approx(0.0)

    moved = tracker.score(shifted)
    assert moved >= 0.0


def test_raw_flow_score_identical_frames_near_zero():
    config = _motion_config()
    frame = np.random.default_rng(0).integers(0, 40, size=(48, 64, 3), dtype=np.uint8)
    gray = prepare_gray(frame, config.flow_scale)
    score = raw_flow_score(gray, gray, config)
    assert score == pytest.approx(0.0, abs=1e-3)


def test_live_motion_tracker_reset_clears_state():
    config = _motion_config()
    tracker = LiveMotionTracker(config)
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    tracker.prime(frame)
    tracker.score(frame)
    tracker.reset()
    assert tracker.smoothed() == 0.0
