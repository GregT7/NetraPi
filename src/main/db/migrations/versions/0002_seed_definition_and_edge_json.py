"""seed definition and edge json

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-15 19:30:00.000000

Frozen snapshot of src/main/edge/config JSON plus classification_type lookup rows.
Do not load live JSON at upgrade time; a later config freeze is a new data revision.

Primary keys are assigned by the database (no explicit ids) so PostgreSQL SERIAL
sequences stay in sync. FKs are wired by looking up rows after insert.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MASTER_NAME = "edge-json"
_OBJECT_LABEL_VALUE = "stop sign"
_SELECTED_MODE_KEY = "mjpeg_640x480_30"

_classification_type = sa.table(
    "classification_type",
    sa.column("value", sa.String),
    sa.column("is_unsafe", sa.Boolean),
    sa.column("auto_stage1", sa.Boolean),
    sa.column("auto_stage2", sa.Boolean),
    sa.column("manual", sa.Boolean),
    sa.column("note", sa.String),
)
_object_label = sa.table(
    "object_label",
    sa.column("value", sa.String),
)
_master_config = sa.table(
    "master_config",
    sa.column("name", sa.String),
    sa.column("created_at", sa.DateTime),
    sa.column("note", sa.String),
)
_camera_config = sa.table(
    "camera_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("device", sa.String),
    sa.column("ndim", sa.Integer),
    sa.column("channels", sa.Integer),
    sa.column("note", sa.String),
)
_camera_mode = sa.table(
    "camera_mode",
    sa.column("camera_config_id", sa.Integer),
    sa.column("mode_key", sa.String),
    sa.column("label", sa.String),
    sa.column("input_format", sa.String),
    sa.column("width", sa.Integer),
    sa.column("height", sa.Integer),
    sa.column("spec_fps", sa.Float),
    sa.column("recommended_fps", sa.Float),
)
_preview_config = sa.table(
    "preview_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("window_name", sa.String),
    sa.column("window_x", sa.Integer),
    sa.column("window_y", sa.Integer),
    sa.column("max_width", sa.Integer),
    sa.column("max_height", sa.Integer),
    sa.column("enabled", sa.Boolean),
    sa.column("toggle_key", sa.String),
)
_detector_config = sa.table(
    "detector_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("model_path", sa.String),
    sa.column("labels_path", sa.String),
    sa.column("input_width", sa.Integer),
    sa.column("input_height", sa.Integer),
    sa.column("channels", sa.Integer),
    sa.column("input_dtype", sa.String),
    sa.column("score_threshold", sa.Float),
    sa.column("top_k", sa.Integer),
    sa.column("note", sa.String),
)
_detector_allowed_class = sa.table(
    "detector_allowed_class",
    sa.column("detector_config_id", sa.Integer),
    sa.column("object_label_id", sa.Integer),
)
_event_manager_config = sa.table(
    "event_manager_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("area_history_seconds", sa.Float),
    sa.column("note", sa.String),
)
_event_trigger_label = sa.table(
    "event_trigger_label",
    sa.column("event_manager_config_id", sa.Integer),
    sa.column("object_label_id", sa.Integer),
)
_approach_config = sa.table(
    "approach_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("min_peak_pct", sa.Float),
    sa.column("min_approach_s", sa.Float),
    sa.column("max_approach_s", sa.Float),
    sa.column("approach_start_peak_ratio", sa.Float),
    sa.column("min_increasing_fraction", sa.Float),
    sa.column("min_log_linear_r2", sa.Float),
    sa.column("drop_within_s", sa.Float),
    sa.column("drop_to_peak_ratio", sa.Float),
    sa.column("post_drop_peak_ratio", sa.Float),
    sa.column("post_drop_hold_s", sa.Float),
)
_motion_config = sa.table(
    "motion_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("flow_scale", sa.Float),
    sa.column("motion_smoothing_window", sa.Integer),
    sa.column("stopped_motion_threshold", sa.Float),
    sa.column("crawl_motion_threshold", sa.Float),
    sa.column("post_drop_window_s", sa.Float),
)
_motion_roi = sa.table(
    "motion_roi",
    sa.column("motion_config_id", sa.Integer),
    sa.column("x_min", sa.Float),
    sa.column("x_max", sa.Float),
    sa.column("y_min", sa.Float),
    sa.column("y_max", sa.Float),
)
_farneback_config = sa.table(
    "farneback_config",
    sa.column("motion_config_id", sa.Integer),
    sa.column("pyr_scale", sa.Float),
    sa.column("levels", sa.Integer),
    sa.column("winsize", sa.Integer),
    sa.column("iterations", sa.Integer),
    sa.column("poly_n", sa.Integer),
    sa.column("poly_sigma", sa.Float),
)
_knn_config = sa.table(
    "knn_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("k_neighbors", sa.Integer),
    sa.column("stage1_model_path", sa.String),
    sa.column("stage2_model_path", sa.String),
)
_knn_feature = sa.table(
    "knn_feature",
    sa.column("knn_config_id", sa.Integer),
    sa.column("stage", sa.Integer),
    sa.column("order_index", sa.Integer),
    sa.column("feature_name", sa.String),
)
_recording_manager_config = sa.table(
    "recording_manager_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("clips_dir", sa.String),
    sa.column("pre_roll_seconds", sa.Float),
    sa.column("post_roll_seconds", sa.Float),
    sa.column("coverage_tolerance", sa.Float),
    sa.column("record_safe_events", sa.Boolean),
    sa.column("ffmpeg_crf", sa.Integer),
    sa.column("note", sa.String),
)
_display_config = sa.table(
    "display_config",
    sa.column("recording_manager_config_id", sa.Integer),
    sa.column("contrast", sa.Float),
    sa.column("tone_enabled", sa.Boolean),
    sa.column("tone_brightness", sa.Float),
)
_trip_recorder_config = sa.table(
    "trip_recorder_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("enabled", sa.Boolean),
    sa.column("segments_dir", sa.String),
    sa.column("segment_seconds", sa.Integer),
    sa.column("ffmpeg_crf", sa.Integer),
    sa.column("note", sa.String),
)
_buzzer_config = sa.table(
    "buzzer_config",
    sa.column("master_config_id", sa.Integer),
    sa.column("gpio_pin", sa.Integer),
    sa.column("volume", sa.Float),
    sa.column("pitch", sa.Float),
    sa.column("duration_seconds", sa.Float),
    sa.column("play_on_unsafe", sa.Boolean),
    sa.column("play_on_safe", sa.Boolean),
)

_CAMERA_MODES: list[dict[str, Any]] = [
    {
        "mode_key": "mjpeg_1600x1200_30",
        "label": "MJPEG 1600x1200 @ 30 fps",
        "input_format": "mjpeg",
        "width": 1600,
        "height": 1200,
        "spec_fps": 30.0,
        "recommended_fps": 30.0,
    },
    {
        "mode_key": "mjpeg_3264x2448_15",
        "label": "MJPEG 3264x2448 @ 15 fps",
        "input_format": "mjpeg",
        "width": 3264,
        "height": 2448,
        "spec_fps": 15.0,
        "recommended_fps": 15.0,
    },
    {
        "mode_key": "mjpeg_2592x1944_15",
        "label": "MJPEG 2592x1944 @ 15 fps",
        "input_format": "mjpeg",
        "width": 2592,
        "height": 1944,
        "spec_fps": 15.0,
        "recommended_fps": 15.0,
    },
    {
        "mode_key": "mjpeg_1920x1080_30",
        "label": "MJPEG 1920x1080 @ 30 fps",
        "input_format": "mjpeg",
        "width": 1920,
        "height": 1080,
        "spec_fps": 30.0,
        "recommended_fps": 30.0,
    },
    {
        "mode_key": "mjpeg_1280x720_30",
        "label": "MJPEG 1280x720 @ 30 fps",
        "input_format": "mjpeg",
        "width": 1280,
        "height": 720,
        "spec_fps": 30.0,
        "recommended_fps": 30.0,
    },
    {
        "mode_key": "mjpeg_800x600_30",
        "label": "MJPEG 800x600 @ 30 fps",
        "input_format": "mjpeg",
        "width": 800,
        "height": 600,
        "spec_fps": 30.0,
        "recommended_fps": 30.0,
    },
    {
        "mode_key": "mjpeg_640x480_30",
        "label": "MJPEG 640x480 @ 30 fps",
        "input_format": "mjpeg",
        "width": 640,
        "height": 480,
        "spec_fps": 30.0,
        "recommended_fps": 30.0,
    },
    {
        "mode_key": "yuyv_1280x720_10",
        "label": "YUYV 1280x720 @ 10 fps",
        "input_format": "yuyv422",
        "width": 1280,
        "height": 720,
        "spec_fps": 10.0,
        "recommended_fps": 10.0,
    },
    {
        "mode_key": "yuyv_800x600_10",
        "label": "YUYV 800x600 @ 10 fps",
        "input_format": "yuyv422",
        "width": 800,
        "height": 600,
        "spec_fps": 10.0,
        "recommended_fps": 10.0,
    },
    {
        "mode_key": "yuyv_640x480_10",
        "label": "YUYV 640x480 @ 10 fps",
        "input_format": "yuyv422",
        "width": 640,
        "height": 480,
        "spec_fps": 10.0,
        "recommended_fps": 10.0,
    },
    {
        "mode_key": "yuyv_320x240_10",
        "label": "YUYV 320x240 @ 10 fps",
        "input_format": "yuyv422",
        "width": 320,
        "height": 240,
        "spec_fps": 10.0,
        "recommended_fps": 10.0,
    },
]


def _one_id(sql: str, **params: Any) -> int:
    row = op.get_bind().execute(sa.text(sql), params).fetchone()
    if row is None or row[0] is None:
        raise RuntimeError(f"expected one id from: {sql!r} params={params!r}")
    return int(row[0])


def upgrade() -> None:
    op.bulk_insert(
        _classification_type,
        [
            {
                "value": "complete-stop",
                "is_unsafe": False,
                "auto_stage1": True,
                "auto_stage2": False,
                "manual": True,
                "note": "Vehicle fully stopped. Also the auto final label when stage 1 is complete-stop.",
            },
            {
                "value": "rolling-stop",
                "is_unsafe": True,
                "auto_stage1": False,
                "auto_stage2": True,
                "manual": True,
                "note": "Slowed but did not stop. Also the auto final label when stage 2 picks this.",
            },
            {
                "value": "run-through",
                "is_unsafe": True,
                "auto_stage1": False,
                "auto_stage2": True,
                "manual": True,
                "note": "Did not stop / treated as a yield. Also the auto final label when stage 2 picks this.",
            },
            {
                "value": "rolling-or-run-through",
                "is_unsafe": True,
                "auto_stage1": True,
                "auto_stage2": False,
                "manual": False,
                "note": "Unsafe bucket before stage 2. Not a review label and not a frontend filter.",
            },
            {
                "value": "false_positive",
                "is_unsafe": False,
                "auto_stage1": False,
                "auto_stage2": False,
                "manual": True,
                "note": "Pipeline created an event, but review says this was not a stop-sign encounter.",
            },
            {
                "value": "false_negative",
                "is_unsafe": False,
                "auto_stage1": False,
                "auto_stage2": False,
                "manual": True,
                "note": "Stop-sign encounter found in trip footage that the pipeline missed.",
            },
        ],
    )
    op.bulk_insert(_object_label, [{"value": _OBJECT_LABEL_VALUE}])
    object_label_id = _one_id(
        "SELECT id FROM object_label WHERE value = :value",
        value=_OBJECT_LABEL_VALUE,
    )

    op.bulk_insert(
        _master_config,
        [
            {
                "name": _MASTER_NAME,
                "created_at": datetime(2026, 8, 15, 0, 0, 0),
                "note": "Frozen snapshot of src/main/edge/config at revision 0002.",
            }
        ],
    )
    master_id = _one_id(
        "SELECT id FROM master_config WHERE name = :name",
        name=_MASTER_NAME,
    )

    op.bulk_insert(
        _camera_config,
        [
            {
                "master_config_id": master_id,
                "device": "/dev/video0",
                "ndim": 3,
                "channels": 3,
                "note": (
                    "Modes from v4l2-ctl -d /dev/video0 --list-formats-ext "
                    "(USB camera on video0). spec_fps = vendor-listed rate for that "
                    "format/resolution. recommended_fps = sustained capture rate measured "
                    "on the deployment Pi (update via TP-13). recommended_fps is applied "
                    "to CAP_PROP_FPS at open; clip/trip MP4 fps is computed from capture "
                    "timestamps at encode time."
                ),
            }
        ],
    )
    camera_id = _one_id(
        "SELECT id FROM camera_config WHERE master_config_id = :mid",
        mid=master_id,
    )
    op.bulk_insert(
        _camera_mode,
        [{**mode, "camera_config_id": camera_id} for mode in _CAMERA_MODES],
    )
    selected_mode_id = _one_id(
        "SELECT id FROM camera_mode WHERE camera_config_id = :cid AND mode_key = :key",
        cid=camera_id,
        key=_SELECTED_MODE_KEY,
    )
    op.execute(
        sa.text(
            "UPDATE camera_config SET selected_camera_mode_id = :mode_id WHERE id = :cid"
        ).bindparams(mode_id=selected_mode_id, cid=camera_id)
    )

    op.bulk_insert(
        _preview_config,
        [
            {
                "master_config_id": master_id,
                "window_name": "NetraPi Preview",
                "window_x": 0,
                "window_y": 0,
                "max_width": 1280,
                "max_height": 720,
                "enabled": True,
                "toggle_key": "t",
            }
        ],
    )
    op.bulk_insert(
        _detector_config,
        [
            {
                "master_config_id": master_id,
                "model_path": "src/main/edge/models/ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite",
                "labels_path": "src/main/edge/models/coco_labels.txt",
                "input_width": 320,
                "input_height": 320,
                "channels": 3,
                "input_dtype": "uint8",
                "score_threshold": 0.5,
                "top_k": 5,
                "note": (
                    "Paths relative to repo root (resolved in main.py). "
                    "input_width/height/channels and input_dtype match "
                    "ssdlite_mobiledet_coco Edge TPU model (uint8, RGB)."
                ),
            }
        ],
    )
    detector_id = _one_id(
        "SELECT id FROM detector_config WHERE master_config_id = :mid",
        mid=master_id,
    )
    op.bulk_insert(
        _detector_allowed_class,
        [{"detector_config_id": detector_id, "object_label_id": object_label_id}],
    )

    op.bulk_insert(
        _event_manager_config,
        [
            {
                "master_config_id": master_id,
                "area_history_seconds": 20.0,
                "note": (
                    "EventManager approach + motion + kNN. trigger_labels: detector "
                    "classifications used for area series. Score filtering uses "
                    "detector.json score_threshold only."
                ),
            }
        ],
    )
    event_manager_id = _one_id(
        "SELECT id FROM event_manager_config WHERE master_config_id = :mid",
        mid=master_id,
    )
    op.bulk_insert(
        _event_trigger_label,
        [
            {
                "event_manager_config_id": event_manager_id,
                "object_label_id": object_label_id,
            }
        ],
    )

    op.bulk_insert(
        _approach_config,
        [
            {
                "master_config_id": master_id,
                "min_peak_pct": 0.25,
                "min_approach_s": 0.35,
                "max_approach_s": 12.0,
                "approach_start_peak_ratio": 0.1,
                "min_increasing_fraction": 0.5,
                "min_log_linear_r2": 0.3,
                "drop_within_s": 2.5,
                "drop_to_peak_ratio": 0.12,
                "post_drop_peak_ratio": 2.5,
                "post_drop_hold_s": 0.05,
            }
        ],
    )
    op.bulk_insert(
        _motion_config,
        [
            {
                "master_config_id": master_id,
                "flow_scale": 0.5,
                "motion_smoothing_window": 5,
                "stopped_motion_threshold": 0.6,
                "crawl_motion_threshold": 2.5,
                "post_drop_window_s": 5.0,
            }
        ],
    )
    motion_id = _one_id(
        "SELECT id FROM motion_config WHERE master_config_id = :mid",
        mid=master_id,
    )
    op.bulk_insert(
        _motion_roi,
        [
            {
                "motion_config_id": motion_id,
                "x_min": 0.25,
                "x_max": 0.75,
                "y_min": 0.55,
                "y_max": 0.95,
            }
        ],
    )
    op.bulk_insert(
        _farneback_config,
        [
            {
                "motion_config_id": motion_id,
                "pyr_scale": 0.5,
                "levels": 3,
                "winsize": 15,
                "iterations": 3,
                "poly_n": 5,
                "poly_sigma": 1.2,
            }
        ],
    )

    op.bulk_insert(
        _knn_config,
        [
            {
                "master_config_id": master_id,
                "k_neighbors": 3,
                "stage1_model_path": "src/main/edge/models/knn_stage1.joblib",
                "stage2_model_path": "src/main/edge/models/knn_stage2.joblib",
            }
        ],
    )
    knn_id = _one_id(
        "SELECT id FROM knn_config WHERE master_config_id = :mid",
        mid=master_id,
    )
    op.bulk_insert(
        _knn_feature,
        [
            {
                "knn_config_id": knn_id,
                "stage": 1,
                "order_index": 0,
                "feature_name": "post_drop_mean_motion",
            },
            {
                "knn_config_id": knn_id,
                "stage": 1,
                "order_index": 1,
                "feature_name": "post_drop_min_motion",
            },
            {
                "knn_config_id": knn_id,
                "stage": 1,
                "order_index": 2,
                "feature_name": "post_drop_p95_motion",
            },
            {
                "knn_config_id": knn_id,
                "stage": 1,
                "order_index": 3,
                "feature_name": "post_drop_stop_fraction",
            },
            {
                "knn_config_id": knn_id,
                "stage": 2,
                "order_index": 0,
                "feature_name": "post_drop_min_motion",
            },
            {
                "knn_config_id": knn_id,
                "stage": 2,
                "order_index": 1,
                "feature_name": "approach_area_sum_pct",
            },
        ],
    )

    op.bulk_insert(
        _recording_manager_config,
        [
            {
                "master_config_id": master_id,
                "clips_dir": "src/main/data/clips",
                "pre_roll_seconds": 10.0,
                "post_roll_seconds": 10.0,
                "coverage_tolerance": 0.95,
                "record_safe_events": True,
                "ffmpeg_crf": 20,
                "note": (
                    "Clip timing, output path, display pixels. MP4 output uses ffmpeg "
                    "H.264 (requires ffmpeg on PATH). Unsafe events always begin capture; "
                    "record_safe_events toggles safe (complete stop) events."
                ),
            }
        ],
    )
    recording_id = _one_id(
        "SELECT id FROM recording_manager_config WHERE master_config_id = :mid",
        mid=master_id,
    )
    op.bulk_insert(
        _display_config,
        [
            {
                "recording_manager_config_id": recording_id,
                "contrast": 1.0,
                "tone_enabled": False,
                "tone_brightness": 10.0,
            }
        ],
    )
    op.bulk_insert(
        _trip_recorder_config,
        [
            {
                "master_config_id": master_id,
                "enabled": False,
                "segments_dir": "src/main/data/trips",
                "segment_seconds": 300,
                "ffmpeg_crf": 20,
                "note": (
                    "Trip segments buffer frames in RAM, then encode once per segment "
                    "with ffmpeg H.264 (requires ffmpeg on PATH)."
                ),
            }
        ],
    )
    op.bulk_insert(
        _buzzer_config,
        [
            {
                "master_config_id": master_id,
                "gpio_pin": 18,
                "volume": 50.0,
                "pitch": 1000.0,
                "duration_seconds": 0.3,
                "play_on_unsafe": True,
                "play_on_safe": False,
            }
        ],
    )


def downgrade() -> None:
    # Tear down by natural keys / master_config.name (ids are not assumed).
    op.execute(
        sa.text(
            """
            UPDATE camera_config
            SET selected_camera_mode_id = NULL
            WHERE master_config_id IN (
                SELECT id FROM master_config WHERE name = :name
            )
            """
        ).bindparams(name=_MASTER_NAME)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM display_config
            WHERE recording_manager_config_id IN (
                SELECT id FROM recording_manager_config
                WHERE master_config_id IN (
                    SELECT id FROM master_config WHERE name = :name
                )
            )
            """
        ).bindparams(name=_MASTER_NAME)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM knn_feature
            WHERE knn_config_id IN (
                SELECT id FROM knn_config
                WHERE master_config_id IN (
                    SELECT id FROM master_config WHERE name = :name
                )
            )
            """
        ).bindparams(name=_MASTER_NAME)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM farneback_config
            WHERE motion_config_id IN (
                SELECT id FROM motion_config
                WHERE master_config_id IN (
                    SELECT id FROM master_config WHERE name = :name
                )
            )
            """
        ).bindparams(name=_MASTER_NAME)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM motion_roi
            WHERE motion_config_id IN (
                SELECT id FROM motion_config
                WHERE master_config_id IN (
                    SELECT id FROM master_config WHERE name = :name
                )
            )
            """
        ).bindparams(name=_MASTER_NAME)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM event_trigger_label
            WHERE event_manager_config_id IN (
                SELECT id FROM event_manager_config
                WHERE master_config_id IN (
                    SELECT id FROM master_config WHERE name = :name
                )
            )
            """
        ).bindparams(name=_MASTER_NAME)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM detector_allowed_class
            WHERE detector_config_id IN (
                SELECT id FROM detector_config
                WHERE master_config_id IN (
                    SELECT id FROM master_config WHERE name = :name
                )
            )
            """
        ).bindparams(name=_MASTER_NAME)
    )
    op.execute(
        sa.text(
            """
            DELETE FROM camera_mode
            WHERE camera_config_id IN (
                SELECT id FROM camera_config
                WHERE master_config_id IN (
                    SELECT id FROM master_config WHERE name = :name
                )
            )
            """
        ).bindparams(name=_MASTER_NAME)
    )
    for table in (
        "buzzer_config",
        "trip_recorder_config",
        "recording_manager_config",
        "knn_config",
        "motion_config",
        "approach_config",
        "event_manager_config",
        "detector_config",
        "preview_config",
        "camera_config",
    ):
        op.execute(
            sa.text(
                f"""
                DELETE FROM {table}
                WHERE master_config_id IN (
                    SELECT id FROM master_config WHERE name = :name
                )
                """
            ).bindparams(name=_MASTER_NAME)
        )
    op.execute(
        sa.text("DELETE FROM master_config WHERE name = :name").bindparams(
            name=_MASTER_NAME
        )
    )
    op.execute(
        sa.text("DELETE FROM object_label WHERE value = :value").bindparams(
            value=_OBJECT_LABEL_VALUE
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM classification_type
            WHERE value IN (
                'complete-stop',
                'rolling-stop',
                'run-through',
                'rolling-or-run-through',
                'false_positive',
                'false_negative'
            )
            """
        )
    )
