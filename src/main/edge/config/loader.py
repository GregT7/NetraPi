from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.types import (
    ApproachConfig,
    BuzzerConfig,
    CameraConfig,
    DetectorConfig,
    EventManagerConfig,
    KnnConfig,
    MotionConfig,
    PreviewConfig,
    RecordingManagerConfig,
    TripRecorderConfig,
)


class ConfigError(Exception):
    """Raised when config files are missing, malformed, or fail validation."""


_CONFIG_PARSERS: tuple[tuple[str, type], ...] = (
    ("camera.json", CameraConfig),
    ("preview.json", PreviewConfig),
    ("detector.json", DetectorConfig),
    ("event_manager.json", EventManagerConfig),
    ("approach_config.json", ApproachConfig),
    ("motion_config.json", MotionConfig),
    ("knn_config.json", KnnConfig),
    ("recording_manager.json", RecordingManagerConfig),
    ("trip_recorder.json", TripRecorderConfig),
    ("buzzer.json", BuzzerConfig),
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    if not path.is_file():
        raise ConfigError(f"Config path is not a file: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Unable to read config file {path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Config root in {path} must be a JSON object")

    return data


def _load_domain_config(config_dir: Path, filename: str, parser: type) -> object:
    path = config_dir / filename
    try:
        data = load_json(path)
        return parser.from_json(data, source=filename)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


@dataclass(frozen=True)
class AppConfig:
    config_dir: Path
    camera: CameraConfig
    preview: PreviewConfig
    detector: DetectorConfig
    event_manager: EventManagerConfig
    approach: ApproachConfig
    motion: MotionConfig
    knn: KnnConfig
    recording_manager: RecordingManagerConfig
    trip_recorder: TripRecorderConfig
    buzzer: BuzzerConfig

    @classmethod
    def load(cls, config_dir: Path) -> AppConfig:
        if not config_dir.exists():
            raise ConfigError(f"Config directory not found: {config_dir}")
        if not config_dir.is_dir():
            raise ConfigError(f"Config path is not a directory: {config_dir}")

        resolved_dir = config_dir.resolve()
        loaded = [_load_domain_config(resolved_dir, filename, parser) for filename, parser in _CONFIG_PARSERS]

        return cls(
            config_dir=resolved_dir,
            camera=loaded[0],  # type: ignore[arg-type]
            preview=loaded[1],  # type: ignore[arg-type]
            detector=loaded[2],  # type: ignore[arg-type]
            event_manager=loaded[3],  # type: ignore[arg-type]
            approach=loaded[4],  # type: ignore[arg-type]
            motion=loaded[5],  # type: ignore[arg-type]
            knn=loaded[6],  # type: ignore[arg-type]
            recording_manager=loaded[7],  # type: ignore[arg-type]
            trip_recorder=loaded[8],  # type: ignore[arg-type]
            buzzer=loaded[9],  # type: ignore[arg-type]
        )
