from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, UniqueConstraint
from sqlmodel import Field, SQLModel


# --- Operational tables ---


class ClassificationType(SQLModel, table=True):
    __tablename__ = "classification_type"

    id: int | None = Field(default=None, primary_key=True)
    value: str = Field(unique=True)
    is_unsafe: bool
    auto_stage1: bool
    auto_stage2: bool
    manual: bool
    note: str


class ObjectLabel(SQLModel, table=True):
    """Detector / trigger class name (e.g. stop sign). Shared so the string is stored once."""

    __tablename__ = "object_label"

    id: int | None = Field(default=None, primary_key=True)
    value: str = Field(unique=True)


class MasterConfig(SQLModel, table=True):
    __tablename__ = "master_config"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime
    note: str


class DrivingSession(SQLModel, table=True):
    __tablename__ = "driving_session"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id")
    start_time: datetime
    end_time: datetime | None = None


class TripSegment(SQLModel, table=True):
    __tablename__ = "trip_segment"

    id: int | None = Field(default=None, primary_key=True)
    driving_session_id: int = Field(foreign_key="driving_session.id")
    local_path: str | None = None
    s3_key: str | None = None
    init_local_stored: bool | None = None
    init_local_deleted: bool | None = None
    s3_stored: bool | None = None
    file_size_bytes: int | None = None
    start_time: datetime
    end_time: datetime
    order_number: int


class OperationalException(SQLModel, table=True):
    __tablename__ = "operational_exception"

    id: int | None = Field(default=None, primary_key=True)
    driving_session_id: int = Field(foreign_key="driving_session.id")
    message: str
    time: datetime
    is_fatal: bool


class Event(SQLModel, table=True):
    __tablename__ = "event"

    id: int | None = Field(default=None, primary_key=True)
    driving_session_id: int = Field(foreign_key="driving_session.id")
    time: datetime


class EventTripLocation(SQLModel, table=True):
    """Optional pointer into trip footage. Session comes from event + trip_segment, not duplicated here."""

    __tablename__ = "event_trip_location"

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", unique=True)
    trip_segment_id: int = Field(foreign_key="trip_segment.id")
    trip_offset_seconds: float


class Clip(SQLModel, table=True):
    __tablename__ = "clip"

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", unique=True)
    local_path: str | None = None
    s3_key: str | None = None
    init_local_stored: bool | None = None
    init_local_deleted: bool | None = None
    s3_stored: bool | None = None
    file_size_bytes: int | None = None
    fps: int
    order_number: int
    num_frames: int
    start_time: datetime
    end_time: datetime


class Classification(SQLModel, table=True):
    __tablename__ = "classification"
    __table_args__ = (
        CheckConstraint("kind IN ('auto', 'manual')", name="ck_classification_kind"),
        UniqueConstraint("event_id", "kind", name="uq_classification_event_kind"),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id")
    classification_type_id: int = Field(foreign_key="classification_type.id")
    kind: str


class ManualClassification(SQLModel, table=True):
    __tablename__ = "manual_classification"

    id: int | None = Field(default=None, primary_key=True)
    classification_id: int = Field(foreign_key="classification.id", unique=True)
    time_of_review: datetime


class AutoClassification(SQLModel, table=True):
    __tablename__ = "auto_classification"

    id: int | None = Field(default=None, primary_key=True)
    classification_id: int = Field(foreign_key="classification.id", unique=True)
    stage1_classification_type_id: int = Field(foreign_key="classification_type.id")
    stage2_classification_type_id: int | None = Field(
        default=None, foreign_key="classification_type.id"
    )


class KnnParameter(SQLModel, table=True):
    __tablename__ = "knn_parameter"
    __table_args__ = (
        UniqueConstraint(
            "auto_classification_id", "knn_feature_id", name="uq_knn_parameter_feature"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    auto_classification_id: int = Field(foreign_key="auto_classification.id")
    knn_feature_id: int = Field(foreign_key="knn_feature.id")
    value: float


class ApproachParameters(SQLModel, table=True):
    __tablename__ = "approach_parameters"

    id: int | None = Field(default=None, primary_key=True)
    auto_classification_id: int = Field(foreign_key="auto_classification.id", unique=True)
    peak_area_pct: float
    approach_duration_s: float
    increasing_fraction: float
    log_linear_r2: float
    drop_duration_s: float
    post_drop_holds: bool


class ApproachFailReason(SQLModel, table=True):
    __tablename__ = "approach_fail_reason"
    __table_args__ = (
        UniqueConstraint(
            "approach_parameters_id", "reason", name="uq_approach_fail_reason"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    approach_parameters_id: int = Field(foreign_key="approach_parameters.id")
    reason: str


# --- Config snapshot tables ---


class CameraConfig(SQLModel, table=True):
    __tablename__ = "camera_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    device: str
    selected_camera_mode_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey(
                "camera_mode.id",
                use_alter=True,
                name="fk_camera_config_selected_mode",
            ),
            nullable=True,
        ),
    )
    ndim: int
    channels: int
    note: str


class CameraMode(SQLModel, table=True):
    __tablename__ = "camera_mode"
    __table_args__ = (
        UniqueConstraint("camera_config_id", "mode_key", name="uq_camera_mode_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    camera_config_id: int = Field(foreign_key="camera_config.id")
    mode_key: str
    label: str
    input_format: str
    width: int
    height: int
    spec_fps: float
    recommended_fps: float


class PreviewConfig(SQLModel, table=True):
    __tablename__ = "preview_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    window_name: str
    window_x: int
    window_y: int
    max_width: int
    max_height: int
    enabled: bool
    toggle_key: str


class DetectorConfig(SQLModel, table=True):
    __tablename__ = "detector_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    model_path: str
    labels_path: str
    input_width: int
    input_height: int
    channels: int
    input_dtype: str
    score_threshold: float
    top_k: int
    note: str


class DetectorAllowedClass(SQLModel, table=True):
    __tablename__ = "detector_allowed_class"
    __table_args__ = (
        UniqueConstraint(
            "detector_config_id", "object_label_id", name="uq_detector_allowed_class"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    detector_config_id: int = Field(foreign_key="detector_config.id")
    object_label_id: int = Field(foreign_key="object_label.id")


class EventManagerConfig(SQLModel, table=True):
    __tablename__ = "event_manager_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    area_history_seconds: float
    note: str


class EventTriggerLabel(SQLModel, table=True):
    __tablename__ = "event_trigger_label"
    __table_args__ = (
        UniqueConstraint(
            "event_manager_config_id",
            "object_label_id",
            name="uq_event_trigger_label",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_manager_config_id: int = Field(foreign_key="event_manager_config.id")
    object_label_id: int = Field(foreign_key="object_label.id")


class ApproachConfig(SQLModel, table=True):
    __tablename__ = "approach_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
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


class MotionConfig(SQLModel, table=True):
    __tablename__ = "motion_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    flow_scale: float
    motion_smoothing_window: int
    stopped_motion_threshold: float
    crawl_motion_threshold: float
    post_drop_window_s: float


class MotionRoi(SQLModel, table=True):
    __tablename__ = "motion_roi"

    id: int | None = Field(default=None, primary_key=True)
    motion_config_id: int = Field(foreign_key="motion_config.id", unique=True)
    x_min: float
    x_max: float
    y_min: float
    y_max: float


class FarnebackConfig(SQLModel, table=True):
    __tablename__ = "farneback_config"

    id: int | None = Field(default=None, primary_key=True)
    motion_config_id: int = Field(foreign_key="motion_config.id", unique=True)
    pyr_scale: float
    levels: int
    winsize: int
    iterations: int
    poly_n: int
    poly_sigma: float


class KnnConfig(SQLModel, table=True):
    __tablename__ = "knn_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    k_neighbors: int
    stage1_model_path: str
    stage2_model_path: str


class KnnFeature(SQLModel, table=True):
    __tablename__ = "knn_feature"
    __table_args__ = (
        UniqueConstraint(
            "knn_config_id", "stage", "order_index", name="uq_knn_feature_order"
        ),
        UniqueConstraint(
            "knn_config_id", "stage", "feature_name", name="uq_knn_feature_name"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    knn_config_id: int = Field(foreign_key="knn_config.id")
    stage: int
    order_index: int
    feature_name: str


class RecordingManagerConfig(SQLModel, table=True):
    __tablename__ = "recording_manager_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    clips_dir: str
    pre_roll_seconds: float
    post_roll_seconds: float
    coverage_tolerance: float
    record_safe_events: bool
    ffmpeg_crf: int
    note: str


class DisplayConfig(SQLModel, table=True):
    __tablename__ = "display_config"

    id: int | None = Field(default=None, primary_key=True)
    recording_manager_config_id: int = Field(
        foreign_key="recording_manager_config.id", unique=True
    )
    contrast: float
    tone_enabled: bool
    tone_brightness: float


class TripRecorderConfig(SQLModel, table=True):
    __tablename__ = "trip_recorder_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    enabled: bool
    segments_dir: str
    segment_seconds: int
    ffmpeg_crf: int
    note: str


class BuzzerConfig(SQLModel, table=True):
    __tablename__ = "buzzer_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    gpio_pin: int
    volume: float
    pitch: float
    duration_seconds: float
    play_on_unsafe: bool
    play_on_safe: bool


class HealthConfig(SQLModel, table=True):
    __tablename__ = "health_config"

    id: int | None = Field(default=None, primary_key=True)
    master_config_id: int = Field(foreign_key="master_config.id", unique=True)
    render_wait_s: float
    render_poll_s: float
    render_request_timeout_s: float
    internet_probe_host: str
    internet_probe_port: int
    internet_probe_timeout_s: float
    public_https_host: str
    public_https_port: int
    wlan_interface: str
    keepalive_interval_s: float
    keepalive_request_timeout_s: float
    keepalive_fail_limit: int
    log_path: str
