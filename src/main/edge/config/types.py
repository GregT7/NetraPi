from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

DetectorInputDtype = Literal["uint8", "float32"]


def _require_key(data: dict[str, Any], key: str, *, source: str) -> Any:
    if key not in data:
        raise ValueError(f"Missing required field '{key}' in {source}")
    return data[key]


def _require_type(value: Any, expected: type | tuple[type, ...], field: str, *, source: str) -> Any:
    if not isinstance(value, expected):
        type_name = getattr(expected, "__name__", str(expected))
        raise ValueError(f"Field '{field}' in {source} must be {type_name}, got {type(value).__name__}")
    return value


def _as_path(value: Any, field: str, *, source: str) -> Path:
    value = _require_type(value, str, field, source=source)
    if not value.strip():
        raise ValueError(f"Field '{field}' in {source} must be a non-empty path")
    return Path(value)


def _as_input_dtype(value: Any, field: str, *, source: str) -> DetectorInputDtype:
    value = _require_type(value, str, field, source=source)
    if value not in ("uint8", "float32"):
        raise ValueError(f"Field '{field}' in {source} must be 'uint8' or 'float32', got {value!r}")
    return value


def _as_label_set(value: Any, field: str, *, source: str) -> set[str]:
    value = _require_type(value, list, field, source=source)
    labels: set[str] = set()
    for index, item in enumerate(value):
        _require_type(item, str, f"{field}[{index}]", source=source)
        labels.add(item)
    return labels


@dataclass(frozen=True)
class CameraConfig:
    device: str
    mode_id: str
    width: int
    height: int
    ndim: int
    channels: int
    spec_fps: float
    recommended_fps: float
    input_format: str

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "camera.json") -> CameraConfig:
        device = _require_type(_require_key(data, "device", source=source), str, "device", source=source)
        mode_id = _require_type(_require_key(data, "mode_id", source=source), str, "mode_id", source=source)
        modes = _require_type(_require_key(data, "modes", source=source), list, "modes", source=source)
        if not modes:
            raise ValueError(f"Field 'modes' in {source} must contain at least one mode")

        selected: dict[str, Any] | None = None
        for index, mode in enumerate(modes):
            _require_type(mode, dict, f"modes[{index}]", source=source)
            if mode.get("id") == mode_id:
                selected = mode
                break

        if selected is None:
            raise ValueError(f"mode_id '{mode_id}' not found in {source} modes[]")

        mode_source = f"{source} modes[{mode_id}]"
        width = int(_require_type(_require_key(selected, "width", source=mode_source), (int, float), "width", source=mode_source))
        height = int(_require_type(_require_key(selected, "height", source=mode_source), (int, float), "height", source=mode_source))
        spec_fps = float(
            _require_type(_require_key(selected, "spec_fps", source=mode_source), (int, float), "spec_fps", source=mode_source)
        )
        recommended_fps = float(
            _require_type(
                _require_key(selected, "recommended_fps", source=mode_source),
                (int, float),
                "recommended_fps",
                source=mode_source,
            )
        )
        if spec_fps <= 0:
            raise ValueError(f"Field 'spec_fps' in {mode_source} must be greater than 0")
        if recommended_fps <= 0:
            raise ValueError(f"Field 'recommended_fps' in {mode_source} must be greater than 0")
        input_format = _require_type(
            _require_key(selected, "input_format", source=mode_source),
            str,
            "input_format",
            source=mode_source,
        )
        if "channels" in selected:
            channels_source = mode_source
            channels_raw = selected["channels"]
        else:
            channels_source = source
            channels_raw = _require_key(data, "channels", source=source)
        channels = int(
            _require_type(channels_raw, (int, float), "channels", source=channels_source)
        )
        if "ndim" in selected:
            ndim_source = mode_source
            ndim_raw = selected["ndim"]
        else:
            ndim_source = source
            ndim_raw = _require_key(data, "ndim", source=source)
        ndim = int(_require_type(ndim_raw, (int, float), "ndim", source=ndim_source))

        return cls(
            device=device,
            mode_id=mode_id,
            width=width,
            height=height,
            ndim=ndim,
            channels=channels,
            spec_fps=spec_fps,
            recommended_fps=recommended_fps,
            input_format=input_format,
        )


@dataclass(frozen=True)
class DisplayConfig:
    """How FrameRecord.display pixels are built for MP4 (and preview when enabled)."""

    contrast: float
    tone_enabled: bool
    tone_brightness: float

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "recording_manager.json display") -> DisplayConfig:
        tone_brightness_raw = data.get("tone_brightness", 10.0)
        return cls(
            contrast=float(
                _require_type(_require_key(data, "contrast", source=source), (int, float), "contrast", source=source)
            ),
            tone_enabled=_require_type(
                _require_key(data, "tone_enabled", source=source),
                bool,
                "tone_enabled",
                source=source,
            ),
            tone_brightness=float(
                _require_type(tone_brightness_raw, (int, float), "tone_brightness", source=source)
            ),
        )


@dataclass(frozen=True)
class RecordingManagerConfig:
    clips_dir: Path
    pre_roll_seconds: float
    post_roll_seconds: float
    coverage_tolerance: float
    display: DisplayConfig
    record_safe_events: bool
    ffmpeg_crf: int

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "recording_manager.json") -> RecordingManagerConfig:
        display_raw = _require_type(_require_key(data, "display", source=source), dict, "display", source=source)
        record_safe_raw = data.get("record_safe_events", False)
        ffmpeg_crf = int(
            _require_type(
                _require_key(data, "ffmpeg_crf", source=source),
                (int, float),
                "ffmpeg_crf",
                source=source,
            )
        )
        if ffmpeg_crf < 0:
            raise ValueError(f"Field 'ffmpeg_crf' in {source} must be >= 0")
        return cls(
            clips_dir=_as_path(_require_key(data, "clips_dir", source=source), "clips_dir", source=source),
            pre_roll_seconds=float(
                _require_type(
                    _require_key(data, "pre_roll_seconds", source=source),
                    (int, float),
                    "pre_roll_seconds",
                    source=source,
                )
            ),
            post_roll_seconds=float(
                _require_type(
                    _require_key(data, "post_roll_seconds", source=source),
                    (int, float),
                    "post_roll_seconds",
                    source=source,
                )
            ),
            coverage_tolerance=float(
                _require_type(
                    _require_key(data, "coverage_tolerance", source=source),
                    (int, float),
                    "coverage_tolerance",
                    source=source,
                )
            ),
            display=DisplayConfig.from_json(display_raw, source=f"{source} display"),
            record_safe_events=_require_type(
                record_safe_raw,
                bool,
                "record_safe_events",
                source=source,
            ),
            ffmpeg_crf=ffmpeg_crf,
        )


@dataclass(frozen=True)
class BuzzerPlayOnConfig:
    unsafe: bool
    safe: bool

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "buzzer.json play_on") -> BuzzerPlayOnConfig:
        return cls(
            unsafe=_require_type(_require_key(data, "unsafe", source=source), bool, "unsafe", source=source),
            safe=_require_type(_require_key(data, "safe", source=source), bool, "safe", source=source),
        )


@dataclass(frozen=True)
class BuzzerConfig:
    gpio_pin: int
    volume: float
    pitch: float
    duration_seconds: float
    play_on: BuzzerPlayOnConfig

    @property
    def enabled(self) -> bool:
        return self.play_on.unsafe or self.play_on.safe

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "buzzer.json") -> BuzzerConfig:
        play_on_raw = _require_type(_require_key(data, "play_on", source=source), dict, "play_on", source=source)
        gpio_pin = int(
            _require_type(_require_key(data, "gpio_pin", source=source), (int, float), "gpio_pin", source=source)
        )
        if gpio_pin < 0:
            raise ValueError(f"Field 'gpio_pin' in {source} must be >= 0")
        volume = float(
            _require_type(_require_key(data, "volume", source=source), (int, float), "volume", source=source)
        )
        if volume < 0 or volume > 100:
            raise ValueError(f"Field 'volume' in {source} must be between 0 and 100")
        pitch = float(_require_type(_require_key(data, "pitch", source=source), (int, float), "pitch", source=source))
        if pitch <= 0:
            raise ValueError(f"Field 'pitch' in {source} must be greater than 0")
        duration_seconds = float(
            _require_type(
                _require_key(data, "duration_seconds", source=source),
                (int, float),
                "duration_seconds",
                source=source,
            )
        )
        if duration_seconds <= 0:
            raise ValueError(f"Field 'duration_seconds' in {source} must be greater than 0")

        return cls(
            gpio_pin=gpio_pin,
            volume=volume,
            pitch=pitch,
            duration_seconds=duration_seconds,
            play_on=BuzzerPlayOnConfig.from_json(play_on_raw, source=f"{source} play_on"),
        )


@dataclass(frozen=True)
class TripRecorderConfig:
    enabled: bool
    segments_dir: Path
    segment_seconds: int
    ffmpeg_crf: int

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "trip_recorder.json") -> TripRecorderConfig:
        segment_seconds = int(
            _require_type(
                _require_key(data, "segment_seconds", source=source),
                (int, float),
                "segment_seconds",
                source=source,
            )
        )
        if segment_seconds <= 0:
            raise ValueError(f"Field 'segment_seconds' in {source} must be greater than 0")
        ffmpeg_crf = int(
            _require_type(
                _require_key(data, "ffmpeg_crf", source=source),
                (int, float),
                "ffmpeg_crf",
                source=source,
            )
        )
        if ffmpeg_crf < 0:
            raise ValueError(f"Field 'ffmpeg_crf' in {source} must be >= 0")

        return cls(
            enabled=_require_type(data.get("enabled", False), bool, "enabled", source=source),
            segments_dir=_as_path(_require_key(data, "segments_dir", source=source), "segments_dir", source=source),
            segment_seconds=segment_seconds,
            ffmpeg_crf=ffmpeg_crf,
        )


@dataclass(frozen=True)
class PreviewConfig:
    window_name: str
    window_x: int
    window_y: int
    max_width: int
    max_height: int
    enabled: bool
    toggle_key: str

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "preview.json") -> PreviewConfig:
        enabled_raw = data.get("enabled", True)
        toggle_key = _require_type(
            _require_key(data, "toggle_key", source=source),
            str,
            "toggle_key",
            source=source,
        )
        if len(toggle_key) != 1:
            raise ValueError(f"{source}: toggle_key must be a single character, got {toggle_key!r}")
        return cls(
            window_name=_require_type(
                _require_key(data, "window_name", source=source),
                str,
                "window_name",
                source=source,
            ),
            window_x=int(
                _require_type(_require_key(data, "window_x", source=source), (int, float), "window_x", source=source)
            ),
            window_y=int(
                _require_type(_require_key(data, "window_y", source=source), (int, float), "window_y", source=source)
            ),
            max_width=int(
                _require_type(_require_key(data, "max_width", source=source), (int, float), "max_width", source=source)
            ),
            max_height=int(
                _require_type(_require_key(data, "max_height", source=source), (int, float), "max_height", source=source)
            ),
            enabled=_require_type(enabled_raw, bool, "enabled", source=source),
            toggle_key=toggle_key,
        )


@dataclass(frozen=True)
class DetectorConfig:
    model_path: Path
    labels_path: Path
    input_width: int
    input_height: int
    channels: int
    input_dtype: DetectorInputDtype
    score_threshold: float
    top_k: int
    allowed_classes: set[str]

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "detector.json") -> DetectorConfig:
        return cls(
            model_path=_as_path(_require_key(data, "model_path", source=source), "model_path", source=source),
            labels_path=_as_path(_require_key(data, "labels_path", source=source), "labels_path", source=source),
            input_width=int(
                _require_type(_require_key(data, "input_width", source=source), (int, float), "input_width", source=source)
            ),
            input_height=int(
                _require_type(_require_key(data, "input_height", source=source), (int, float), "input_height", source=source)
            ),
            channels=int(
                _require_type(_require_key(data, "channels", source=source), (int, float), "channels", source=source)
            ),
            input_dtype=_as_input_dtype(_require_key(data, "input_dtype", source=source), "input_dtype", source=source),
            score_threshold=float(
                _require_type(
                    _require_key(data, "score_threshold", source=source),
                    (int, float),
                    "score_threshold",
                    source=source,
                )
            ),
            top_k=int(_require_type(_require_key(data, "top_k", source=source), (int, float), "top_k", source=source)),
            allowed_classes=_as_label_set(
                _require_key(data, "allowed_classes", source=source),
                "allowed_classes",
                source=source,
            ),
        )


@dataclass(frozen=True)
class ApproachConfig:
    min_peak_pct: float
    min_approach_s: float
    max_approach_s: float
    approach_start_peak_ratio: float
    min_increasing_fraction: float
    min_log_linear_r2: float
    drop_within_s: float
    drop_to_peak_ratio: float
    post_drop_peak_ratio: float
    post_drop_hold_s: float

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "approach_config.json") -> ApproachConfig:
        return cls(
            min_peak_pct=float(
                _require_type(
                    _require_key(data, "min_peak_pct", source=source),
                    (int, float),
                    "min_peak_pct",
                    source=source,
                )
            ),
            min_approach_s=float(
                _require_type(
                    _require_key(data, "min_approach_s", source=source),
                    (int, float),
                    "min_approach_s",
                    source=source,
                )
            ),
            max_approach_s=float(
                _require_type(
                    _require_key(data, "max_approach_s", source=source),
                    (int, float),
                    "max_approach_s",
                    source=source,
                )
            ),
            approach_start_peak_ratio=float(
                _require_type(
                    _require_key(data, "approach_start_peak_ratio", source=source),
                    (int, float),
                    "approach_start_peak_ratio",
                    source=source,
                )
            ),
            min_increasing_fraction=float(
                _require_type(
                    _require_key(data, "min_increasing_fraction", source=source),
                    (int, float),
                    "min_increasing_fraction",
                    source=source,
                )
            ),
            min_log_linear_r2=float(
                _require_type(
                    _require_key(data, "min_log_linear_r2", source=source),
                    (int, float),
                    "min_log_linear_r2",
                    source=source,
                )
            ),
            drop_within_s=float(
                _require_type(
                    _require_key(data, "drop_within_s", source=source),
                    (int, float),
                    "drop_within_s",
                    source=source,
                )
            ),
            drop_to_peak_ratio=float(
                _require_type(
                    _require_key(data, "drop_to_peak_ratio", source=source),
                    (int, float),
                    "drop_to_peak_ratio",
                    source=source,
                )
            ),
            post_drop_peak_ratio=float(
                _require_type(
                    _require_key(data, "post_drop_peak_ratio", source=source),
                    (int, float),
                    "post_drop_peak_ratio",
                    source=source,
                )
            ),
            post_drop_hold_s=float(
                _require_type(
                    _require_key(data, "post_drop_hold_s", source=source),
                    (int, float),
                    "post_drop_hold_s",
                    source=source,
                )
            ),
        )


@dataclass(frozen=True)
class MotionConfig:
    motion_roi: dict[str, float]
    flow_scale: float
    motion_smoothing_window: int
    stopped_motion_threshold: float
    crawl_motion_threshold: float
    post_drop_window_s: float
    farneback: dict[str, float | int]

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "motion_config.json") -> MotionConfig:
        roi_raw = _require_type(_require_key(data, "motion_roi", source=source), dict, "motion_roi", source=source)
        farneback_raw = _require_type(_require_key(data, "farneback", source=source), dict, "farneback", source=source)
        roi: dict[str, float] = {}
        for key in ("x_min", "x_max", "y_min", "y_max"):
            roi[key] = float(_require_type(_require_key(roi_raw, key, source=source), (int, float), f"motion_roi.{key}", source=source))
        farneback: dict[str, float | int] = {}
        for key, value in farneback_raw.items():
            if not isinstance(key, str):
                raise ValueError(f"Field 'farneback' keys in {source} must be strings")
            if not isinstance(value, (int, float)):
                raise ValueError(f"Field 'farneback.{key}' in {source} must be a number")
            farneback[key] = value
        smoothing = int(
            _require_type(
                _require_key(data, "motion_smoothing_window", source=source),
                (int, float),
                "motion_smoothing_window",
                source=source,
            )
        )
        if smoothing < 1:
            raise ValueError(f"Field 'motion_smoothing_window' in {source} must be >= 1")
        post_drop = float(
            _require_type(
                _require_key(data, "post_drop_window_s", source=source),
                (int, float),
                "post_drop_window_s",
                source=source,
            )
        )
        if post_drop <= 0:
            raise ValueError(f"Field 'post_drop_window_s' in {source} must be greater than 0")
        return cls(
            motion_roi=roi,
            flow_scale=float(
                _require_type(
                    _require_key(data, "flow_scale", source=source),
                    (int, float),
                    "flow_scale",
                    source=source,
                )
            ),
            motion_smoothing_window=smoothing,
            stopped_motion_threshold=float(
                _require_type(
                    _require_key(data, "stopped_motion_threshold", source=source),
                    (int, float),
                    "stopped_motion_threshold",
                    source=source,
                )
            ),
            crawl_motion_threshold=float(
                _require_type(
                    _require_key(data, "crawl_motion_threshold", source=source),
                    (int, float),
                    "crawl_motion_threshold",
                    source=source,
                )
            ),
            post_drop_window_s=post_drop,
            farneback=farneback,
        )


@dataclass(frozen=True)
class KnnConfig:
    k_neighbors: int
    stage1_feature_names: tuple[str, ...]
    stage2_feature_names: tuple[str, ...]
    stage1_model_path: Path
    stage2_model_path: Path

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "knn_config.json") -> KnnConfig:
        stage1_names = _require_type(
            _require_key(data, "stage1_feature_names", source=source),
            list,
            "stage1_feature_names",
            source=source,
        )
        stage2_names = _require_type(
            _require_key(data, "stage2_feature_names", source=source),
            list,
            "stage2_feature_names",
            source=source,
        )
        for index, name in enumerate(stage1_names):
            _require_type(name, str, f"stage1_feature_names[{index}]", source=source)
        for index, name in enumerate(stage2_names):
            _require_type(name, str, f"stage2_feature_names[{index}]", source=source)
        k_neighbors = int(
            _require_type(
                _require_key(data, "k_neighbors", source=source),
                (int, float),
                "k_neighbors",
                source=source,
            )
        )
        if k_neighbors < 1:
            raise ValueError(f"Field 'k_neighbors' in {source} must be >= 1")
        return cls(
            k_neighbors=k_neighbors,
            stage1_feature_names=tuple(stage1_names),
            stage2_feature_names=tuple(stage2_names),
            stage1_model_path=_as_path(
                _require_key(data, "stage1_model_path", source=source),
                "stage1_model_path",
                source=source,
            ),
            stage2_model_path=_as_path(
                _require_key(data, "stage2_model_path", source=source),
                "stage2_model_path",
                source=source,
            ),
        )


@dataclass(frozen=True)
class EventManagerConfig:
    trigger_labels: set[str]
    area_history_seconds: float

    @classmethod
    def from_json(cls, data: dict[str, Any], *, source: str = "event_manager.json") -> EventManagerConfig:
        area_history = float(
            _require_type(
                _require_key(data, "area_history_seconds", source=source),
                (int, float),
                "area_history_seconds",
                source=source,
            )
        )
        if area_history <= 0:
            raise ValueError(f"Field 'area_history_seconds' in {source} must be greater than 0")
        return cls(
            trigger_labels=_as_label_set(
                _require_key(data, "trigger_labels", source=source),
                "trigger_labels",
                source=source,
            ),
            area_history_seconds=area_history,
        )
