from __future__ import annotations

from pathlib import Path

import pytest

from config.loader import AppConfig
from netrapi.events.approach import ApproachDropEvent
from netrapi.events.classify.features import (
    compute_approach_area_sum_pct,
    extract_stage1_features,
    extract_stage2_features,
)

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "config"


def test_extract_stage1_features_known_window():
    samples = [
        (0.5, 9.0),
        (1.0, 0.2),
        (2.0, 0.4),
        (3.0, 0.8),
        (4.0, 1.0),
        (5.0, 0.3),
        (6.0, 0.1),
        (7.0, 5.0),
    ]
    features = extract_stage1_features(
        samples,
        anchor_s=1.0,
        window_s=5.0,
        stopped_threshold=0.6,
    )

    assert features is not None
    mean, minimum, p95, stop_fraction = features
    window = [0.2, 0.4, 0.8, 1.0, 0.3, 0.1]
    assert mean == pytest.approx(sum(window) / len(window))
    assert minimum == pytest.approx(0.1)
    assert 0.8 <= p95 <= 1.0
    assert stop_fraction == pytest.approx(4 / 6)


def test_extract_stage1_features_empty_window_returns_none():
    assert (
        extract_stage1_features(
            [(0.0, 1.0)],
            anchor_s=10.0,
            window_s=5.0,
            stopped_threshold=0.6,
        )
        is None
    )


def test_compute_approach_area_sum_pct():
    areas = [0.01, 0.02, 0.03, 0.01]
    event = ApproachDropEvent(
        peak_index=2,
        peak_time_s=0.2,
        peak_area_pct=3.0,
        approach_start_index=0,
        approach_start_time_s=0.0,
        approach_start_area_pct=1.0,
        drop_end_index=3,
        drop_end_time_s=0.3,
        drop_end_area_pct=1.0,
        approach_duration_s=0.2,
        drop_duration_s=0.1,
        log_linear_r2=0.9,
        increasing_fraction=1.0,
        score=1.0,
    )
    total = compute_approach_area_sum_pct(areas, event)
    assert total == pytest.approx(sum(a * 100.0 for a in areas))


def test_extract_stage2_features_with_real_approach_prefix():
    approach = AppConfig.load(FIXTURES_DIR).approach
    # Build a series that approach detect accepts (same recipe as test_approach).
    areas: list[float] = [0.0] * 5
    for index in range(20):
        areas.append(0.001 * (1.25**index))
    peak = areas[-1]
    areas.extend([peak * 0.05, peak * 0.02, 0.0, 0.0])

    stage1 = [0.5, 0.1, 0.9, 0.8]
    stage2 = extract_stage2_features(
        stage1_features=stage1,
        areas_snapshot=areas,
        detect_frame=len(areas) - 1,
        fps=10.0,
        approach_config=approach,
    )
    assert stage2 is not None
    assert stage2[0] == pytest.approx(0.1)
    assert stage2[1] > 0.0
