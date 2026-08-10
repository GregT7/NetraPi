from __future__ import annotations

from pathlib import Path

from config.loader import AppConfig
from config.types import ApproachConfig
from netrapi.events.approach import diagnose_approach_drop

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "config"


def _approach_config() -> ApproachConfig:
    return AppConfig.load(FIXTURES_DIR).approach


def _synthetic_grow_peak_drop(*, fps: float = 10.0) -> list[float]:
    """Normalized areas: grow ~2s, peak, then sharp drop (fraction of frame)."""
    areas: list[float] = []
    # Quiet lead-in
    areas.extend([0.0] * 5)
    # Exponential-ish grow from ~0.001 to ~0.01 (0.1% → 1.0%)
    for index in range(20):
        areas.append(0.001 * (1.25**index))
    peak = areas[-1]
    # Sharp drop below 12% of peak
    areas.append(peak * 0.05)
    areas.append(peak * 0.02)
    areas.append(0.0)
    areas.append(0.0)
    return areas


def test_diagnose_approach_drop_fires_on_grow_peak_drop():
    areas = _synthetic_grow_peak_drop()
    diagnosis = diagnose_approach_drop(areas, fps=10.0, config=_approach_config())

    assert diagnosis is not None
    assert diagnosis.event is not None
    assert diagnosis.event.peak_area_pct >= 0.25


def test_diagnose_approach_drop_rejects_noise():
    # Flat low noise never forms a qualifying peak/drop.
    areas = [0.0001 + (0.00005 if index % 2 else 0.0) for index in range(40)]
    diagnosis = diagnose_approach_drop(areas, fps=10.0, config=_approach_config())

    assert diagnosis is not None
    assert diagnosis.event is None


def test_diagnose_approach_drop_empty_series():
    assert diagnose_approach_drop([], fps=10.0, config=_approach_config()) is None


def test_diagnose_approach_drop_requires_positive_fps():
    assert diagnose_approach_drop([0.01, 0.02], fps=0.0, config=_approach_config()) is None
