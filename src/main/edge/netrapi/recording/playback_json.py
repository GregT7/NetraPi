"""Write Style A area/motion/transition sidecars next to an event clip MP4."""

from __future__ import annotations

import json
from pathlib import Path

from netrapi.events.driving_event import PlaybackSeries

PLAYBACK_SCHEMA_VERSION = 1
AREAS_NAME = "areas.json"
MOTION_NAME = "motion.json"
TRANSITIONS_NAME = "transitions.json"
SIDECAR_NAMES = (AREAS_NAME, MOTION_NAME, TRANSITIONS_NAME)


def clip_origin_monotonic(series: PlaybackSeries, *, pre_roll_seconds: float) -> float:
    return series.evaluate_t - pre_roll_seconds


def classification_state_id(classification: str) -> str:
    value = classification.strip().lower()
    if "complete" in value:
        return "CompleteStop"
    if "rolling" in value:
        return "RollingStop"
    if "run" in value:
        return "RunThrough"
    return "CompleteStop"


def write_playback_sidecars(
    clip_path: Path,
    series: PlaybackSeries | None,
    *,
    pre_roll_seconds: float,
    classification: str,
) -> None:
    clip_dir = clip_path.parent
    clip_dir.mkdir(parents=True, exist_ok=True)
    if series is None:
        t0_s = 0.0
        sample_end_s = 0.0
        area_points: list[dict[str, float]] = []
        motion_points: list[dict[str, float]] = []
    else:
        origin = clip_origin_monotonic(series, pre_roll_seconds=pre_roll_seconds)
        t0_s = series.anchor_t - origin
        sample_end_s = series.evaluate_t - origin
        area_points = [
            {"t": round(stamp - origin, 4), "area": value}
            for stamp, value in series.area_points
        ]
        motion_points = [
            {"t": round(stamp - origin, 4), "score": value}
            for stamp, value in series.motion_points
        ]
    meta = {
        "schema_version": PLAYBACK_SCHEMA_VERSION,
        "t0_s": round(t0_s, 4),
        "sample_end_s": round(sample_end_s, 4),
        "classification": classification,
    }
    (clip_dir / AREAS_NAME).write_text(
        json.dumps({**meta, "points": area_points}, indent=2),
        encoding="utf-8",
    )
    (clip_dir / MOTION_NAME).write_text(
        json.dumps({**meta, "points": motion_points}, indent=2),
        encoding="utf-8",
    )
    (clip_dir / TRANSITIONS_NAME).write_text(
        json.dumps(
            {
                "schema_version": PLAYBACK_SCHEMA_VERSION,
                "classification": classification,
                "states": [
                    {"t": 0.0, "id": "Monitoring"},
                    {"t": round(t0_s, 4), "id": "SampleMotion"},
                    {
                        "t": round(sample_end_s, 4),
                        "id": classification_state_id(classification),
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
