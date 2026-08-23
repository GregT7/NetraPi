"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-15 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classification_type",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("is_unsafe", sa.Boolean(), nullable=False),
        sa.Column("auto_stage1", sa.Boolean(), nullable=False),
        sa.Column("auto_stage2", sa.Boolean(), nullable=False),
        sa.Column("manual", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("value"),
    )
    op.create_table(
        "object_label",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("value"),
    )
    op.create_table(
        "master_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "camera_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("device", sa.String(), nullable=False),
        sa.Column("ndim", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "preview_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("window_name", sa.String(), nullable=False),
        sa.Column("window_x", sa.Integer(), nullable=False),
        sa.Column("window_y", sa.Integer(), nullable=False),
        sa.Column("max_width", sa.Integer(), nullable=False),
        sa.Column("max_height", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("toggle_key", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "detector_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("model_path", sa.String(), nullable=False),
        sa.Column("labels_path", sa.String(), nullable=False),
        sa.Column("input_width", sa.Integer(), nullable=False),
        sa.Column("input_height", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("input_dtype", sa.String(), nullable=False),
        sa.Column("score_threshold", sa.Float(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "event_manager_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("area_history_seconds", sa.Float(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "approach_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("min_peak_pct", sa.Float(), nullable=False),
        sa.Column("min_approach_s", sa.Float(), nullable=False),
        sa.Column("max_approach_s", sa.Float(), nullable=False),
        sa.Column("approach_start_peak_ratio", sa.Float(), nullable=False),
        sa.Column("min_increasing_fraction", sa.Float(), nullable=False),
        sa.Column("min_log_linear_r2", sa.Float(), nullable=False),
        sa.Column("drop_within_s", sa.Float(), nullable=False),
        sa.Column("drop_to_peak_ratio", sa.Float(), nullable=False),
        sa.Column("post_drop_peak_ratio", sa.Float(), nullable=False),
        sa.Column("post_drop_hold_s", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "motion_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("flow_scale", sa.Float(), nullable=False),
        sa.Column("motion_smoothing_window", sa.Integer(), nullable=False),
        sa.Column("stopped_motion_threshold", sa.Float(), nullable=False),
        sa.Column("crawl_motion_threshold", sa.Float(), nullable=False),
        sa.Column("post_drop_window_s", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "knn_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("k_neighbors", sa.Integer(), nullable=False),
        sa.Column("stage1_model_path", sa.String(), nullable=False),
        sa.Column("stage2_model_path", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "recording_manager_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("clips_dir", sa.String(), nullable=False),
        sa.Column("pre_roll_seconds", sa.Float(), nullable=False),
        sa.Column("post_roll_seconds", sa.Float(), nullable=False),
        sa.Column("coverage_tolerance", sa.Float(), nullable=False),
        sa.Column("record_safe_events", sa.Boolean(), nullable=False),
        sa.Column("ffmpeg_crf", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "trip_recorder_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("segments_dir", sa.String(), nullable=False),
        sa.Column("segment_seconds", sa.Integer(), nullable=False),
        sa.Column("ffmpeg_crf", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "buzzer_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("gpio_pin", sa.Integer(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("pitch", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("play_on_unsafe", sa.Boolean(), nullable=False),
        sa.Column("play_on_safe", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("master_config_id"),
    )
    op.create_table(
        "driving_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("master_config_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["master_config_id"], ["master_config.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "camera_mode",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("camera_config_id", sa.Integer(), nullable=False),
        sa.Column("mode_key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("input_format", sa.String(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("spec_fps", sa.Float(), nullable=False),
        sa.Column("recommended_fps", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["camera_config_id"], ["camera_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("camera_config_id", "mode_key", name="uq_camera_mode_key"),
    )
    with op.batch_alter_table("camera_config") as batch_op:
        batch_op.add_column(sa.Column("selected_camera_mode_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_camera_config_selected_mode",
            "camera_mode",
            ["selected_camera_mode_id"],
            ["id"],
        )
    op.create_table(
        "detector_allowed_class",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("detector_config_id", sa.Integer(), nullable=False),
        sa.Column("object_label_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["detector_config_id"], ["detector_config.id"]),
        sa.ForeignKeyConstraint(["object_label_id"], ["object_label.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "detector_config_id", "object_label_id", name="uq_detector_allowed_class"
        ),
    )
    op.create_table(
        "event_trigger_label",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_manager_config_id", sa.Integer(), nullable=False),
        sa.Column("object_label_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["event_manager_config_id"], ["event_manager_config.id"]),
        sa.ForeignKeyConstraint(["object_label_id"], ["object_label.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_manager_config_id", "object_label_id", name="uq_event_trigger_label"
        ),
    )
    op.create_table(
        "display_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recording_manager_config_id", sa.Integer(), nullable=False),
        sa.Column("contrast", sa.Float(), nullable=False),
        sa.Column("tone_enabled", sa.Boolean(), nullable=False),
        sa.Column("tone_brightness", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recording_manager_config_id"], ["recording_manager_config.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recording_manager_config_id"),
    )
    op.create_table(
        "farneback_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("motion_config_id", sa.Integer(), nullable=False),
        sa.Column("pyr_scale", sa.Float(), nullable=False),
        sa.Column("levels", sa.Integer(), nullable=False),
        sa.Column("winsize", sa.Integer(), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("poly_n", sa.Integer(), nullable=False),
        sa.Column("poly_sigma", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["motion_config_id"], ["motion_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("motion_config_id"),
    )
    op.create_table(
        "knn_feature",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knn_config_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("feature_name", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["knn_config_id"], ["knn_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "knn_config_id", "stage", "order_index", name="uq_knn_feature_order"
        ),
        sa.UniqueConstraint(
            "knn_config_id", "stage", "feature_name", name="uq_knn_feature_name"
        ),
    )
    op.create_table(
        "motion_roi",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("motion_config_id", sa.Integer(), nullable=False),
        sa.Column("x_min", sa.Float(), nullable=False),
        sa.Column("x_max", sa.Float(), nullable=False),
        sa.Column("y_min", sa.Float(), nullable=False),
        sa.Column("y_max", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["motion_config_id"], ["motion_config.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("motion_config_id"),
    )
    op.create_table(
        "operational_exception",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driving_session_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.Column("is_fatal", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["driving_session_id"], ["driving_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "trip_segment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driving_session_id", sa.Integer(), nullable=False),
        sa.Column("local_path", sa.String(), nullable=True),
        sa.Column("s3_key", sa.String(), nullable=True),
        sa.Column("init_local_stored", sa.Boolean(), nullable=True),
        sa.Column("init_local_deleted", sa.Boolean(), nullable=True),
        sa.Column("s3_stored", sa.Boolean(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["driving_session_id"], ["driving_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driving_session_id", sa.Integer(), nullable=False),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["driving_session_id"], ["driving_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "event_trip_location",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("trip_segment_id", sa.Integer(), nullable=False),
        sa.Column("trip_offset_seconds", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.ForeignKeyConstraint(["trip_segment_id"], ["trip_segment.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_table(
        "classification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("classification_type_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.CheckConstraint("kind IN ('auto', 'manual')", name="ck_classification_kind"),
        sa.ForeignKeyConstraint(["classification_type_id"], ["classification_type.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "kind", name="uq_classification_event_kind"),
    )
    op.create_table(
        "clip",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("local_path", sa.String(), nullable=True),
        sa.Column("s3_key", sa.String(), nullable=True),
        sa.Column("init_local_stored", sa.Boolean(), nullable=True),
        sa.Column("init_local_deleted", sa.Boolean(), nullable=True),
        sa.Column("s3_stored", sa.Boolean(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("fps", sa.Integer(), nullable=False),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.Column("num_frames", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_table(
        "auto_classification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("classification_id", sa.Integer(), nullable=False),
        sa.Column("stage1_classification_type_id", sa.Integer(), nullable=False),
        sa.Column("stage2_classification_type_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["classification_id"], ["classification.id"]),
        sa.ForeignKeyConstraint(
            ["stage1_classification_type_id"], ["classification_type.id"]
        ),
        sa.ForeignKeyConstraint(
            ["stage2_classification_type_id"], ["classification_type.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("classification_id"),
    )
    op.create_table(
        "manual_classification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("classification_id", sa.Integer(), nullable=False),
        sa.Column("time_of_review", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["classification_id"], ["classification.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("classification_id"),
    )
    op.create_table(
        "approach_parameters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("auto_classification_id", sa.Integer(), nullable=False),
        sa.Column("peak_area_pct", sa.Float(), nullable=False),
        sa.Column("approach_duration_s", sa.Float(), nullable=False),
        sa.Column("increasing_fraction", sa.Float(), nullable=False),
        sa.Column("log_linear_r2", sa.Float(), nullable=False),
        sa.Column("drop_duration_s", sa.Float(), nullable=False),
        sa.Column("post_drop_holds", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["auto_classification_id"], ["auto_classification.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("auto_classification_id"),
    )
    op.create_table(
        "approach_fail_reason",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("approach_parameters_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["approach_parameters_id"], ["approach_parameters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "approach_parameters_id", "reason", name="uq_approach_fail_reason"
        ),
    )
    op.create_table(
        "knn_parameter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("auto_classification_id", sa.Integer(), nullable=False),
        sa.Column("knn_feature_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["auto_classification_id"], ["auto_classification.id"]),
        sa.ForeignKeyConstraint(["knn_feature_id"], ["knn_feature.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "auto_classification_id", "knn_feature_id", name="uq_knn_parameter_feature"
        ),
    )


def downgrade() -> None:
    op.drop_table("knn_parameter")
    op.drop_table("approach_fail_reason")
    op.drop_table("approach_parameters")
    op.drop_table("manual_classification")
    op.drop_table("auto_classification")
    op.drop_table("clip")
    op.drop_table("classification")
    op.drop_table("event_trip_location")
    op.drop_table("event")
    op.drop_table("trip_segment")
    op.drop_table("operational_exception")
    op.drop_table("motion_roi")
    op.drop_table("knn_feature")
    op.drop_table("farneback_config")
    op.drop_table("display_config")
    op.drop_table("event_trigger_label")
    op.drop_table("detector_allowed_class")
    with op.batch_alter_table("camera_config") as batch_op:
        batch_op.drop_constraint("fk_camera_config_selected_mode", type_="foreignkey")
        batch_op.drop_column("selected_camera_mode_id")
    op.drop_table("camera_mode")
    op.drop_table("driving_session")
    op.drop_table("buzzer_config")
    op.drop_table("trip_recorder_config")
    op.drop_table("recording_manager_config")
    op.drop_table("knn_config")
    op.drop_table("motion_config")
    op.drop_table("approach_config")
    op.drop_table("event_manager_config")
    op.drop_table("detector_config")
    op.drop_table("preview_config")
    op.drop_table("camera_config")
    op.drop_table("master_config")
    op.drop_table("object_label")
    op.drop_table("classification_type")
