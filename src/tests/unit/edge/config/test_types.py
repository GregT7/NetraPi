import json
from pathlib import Path

import pytest

from config.types import (
    ApproachConfig,
    BuzzerConfig,
    BuzzerPlayOnConfig,
    CameraConfig,
    DetectorConfig,
    DisplayConfig,
    EventManagerConfig,
    HealthConfig,
    KnnConfig,
    MotionConfig,
    PreviewConfig,
    RecordingManagerConfig,
    TripRecorderConfig,
)

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "config"


def test_camera_config_from_json_selects_mode():
    data = {
        "device": "/dev/video0",
        "ndim": 3,
        "channels": 3,
        "mode_id": "mjpeg_640x480_30",
        "modes": [
            {
                "id": "mjpeg_1280x720_30",
                "input_format": "mjpeg",
                "width": 1280,
                "height": 720,
                "spec_fps": 30.0,
                "recommended_fps": 30.0,
            },
            {
                "id": "mjpeg_640x480_30",
                "input_format": "mjpeg",
                "width": 640,
                "height": 480,
                "spec_fps": 30.0,
                "recommended_fps": 29.5,
            },
        ],
    }

    config = CameraConfig.from_json(data)

    assert config.device == "/dev/video0"
    assert config.mode_id == "mjpeg_640x480_30"
    assert config.width == 640
    assert config.height == 480
    assert config.ndim == 3
    assert config.channels == 3
    assert config.spec_fps == 30.0
    assert config.recommended_fps == 29.5
    assert config.input_format == "mjpeg"


def test_camera_config_requires_recommended_fps():
    data = {
        "device": "/dev/video0",
        "ndim": 3,
        "channels": 3,
        "mode_id": "mode_a",
        "modes": [
            {
                "id": "mode_a",
                "input_format": "mjpeg",
                "width": 640,
                "height": 480,
                "spec_fps": 15.0,
            }
        ],
    }

    with pytest.raises(ValueError, match="recommended_fps"):
        CameraConfig.from_json(data)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "Missing required field 'device'"),
        ({"device": "/dev/video0"}, "Missing required field 'mode_id'"),
        (
            {"device": "/dev/video0", "mode_id": "missing", "modes": []},
            "Field 'modes' in camera.json must contain at least one mode",
        ),
        (
            {"device": "/dev/video0", "mode_id": "missing", "modes": [{"id": "other"}]},
            "mode_id 'missing' not found",
        ),
    ],
)
def test_camera_config_from_json_invalid(data, message):
    with pytest.raises(ValueError, match=message):
        CameraConfig.from_json(data)


def test_recording_manager_config_from_json():
    config = RecordingManagerConfig.from_json(
        {
            "clips_dir": "data/clips",
            "pre_roll_seconds": 10,
            "post_roll_seconds": 8.5,
            "coverage_tolerance": 0.95,
            "display": {"contrast": 1.0, "tone_enabled": False},
            "record_safe_events": False,
            "ffmpeg_crf": 20,
        }
    )

    assert config.clips_dir == Path("data/clips")
    assert config.pre_roll_seconds == 10.0
    assert config.post_roll_seconds == 8.5
    assert config.coverage_tolerance == pytest.approx(0.95)
    assert config.display.contrast == 1.0
    assert config.display.tone_enabled is False
    assert config.record_safe_events is False
    assert config.ffmpeg_crf == 20


def test_display_config_defaults_tone_brightness():
    config = DisplayConfig.from_json({"contrast": 1.0, "tone_enabled": True})

    assert config.tone_brightness == 10.0


def test_preview_config_from_json():
    config = PreviewConfig.from_json(
        {
            "window_name": "NetraPi Preview",
            "window_x": 0,
            "window_y": 0,
            "max_width": 1280,
            "max_height": 720,
            "enabled": False,
            "toggle_key": "t",
        }
    )

    assert config.window_name == "NetraPi Preview"
    assert config.window_x == 0
    assert config.window_y == 0
    assert config.max_width == 1280
    assert config.max_height == 720
    assert config.enabled is False
    assert config.toggle_key == "t"


def test_preview_config_defaults_enabled():
    config = PreviewConfig.from_json(
        {
            "window_name": "NetraPi Preview",
            "window_x": 0,
            "window_y": 0,
            "max_width": 1280,
            "max_height": 720,
            "toggle_key": "t",
        }
    )

    assert config.enabled is True


def test_detector_config_from_json():
    config = DetectorConfig.from_json(
        {
            "model_path": "models/model.tflite",
            "labels_path": "models/labels.txt",
            "input_width": 320,
            "input_height": 320,
            "channels": 3,
            "input_dtype": "uint8",
            "score_threshold": 0.5,
            "top_k": 5,
            "allowed_classes": ["stop sign", "car"],
        }
    )

    assert config.model_path == Path("models/model.tflite")
    assert config.labels_path == Path("models/labels.txt")
    assert config.input_width == 320
    assert config.input_height == 320
    assert config.channels == 3
    assert config.input_dtype == "uint8"
    assert config.score_threshold == 0.5
    assert config.top_k == 5
    assert config.allowed_classes == {"stop sign", "car"}


def test_event_manager_config_from_json():
    config = EventManagerConfig.from_json(
        {"trigger_labels": ["stop sign"], "area_history_seconds": 20.0}
    )

    assert config.trigger_labels == {"stop sign"}
    assert config.area_history_seconds == 20.0


def test_approach_config_from_json():
    config = ApproachConfig.from_json(
        json.loads((FIXTURES_DIR / "approach_config.json").read_text(encoding="utf-8"))
    )

    assert config.min_peak_pct == 0.25
    assert config.drop_within_s == 2.5
    assert config.post_drop_hold_s == 0.05


def test_motion_config_from_json():
    config = MotionConfig.from_json(
        json.loads((FIXTURES_DIR / "motion_config.json").read_text(encoding="utf-8"))
    )

    assert config.stopped_motion_threshold == 0.6
    assert config.post_drop_window_s == 5.0
    assert config.motion_roi["y_min"] == 0.55
    assert config.farneback["winsize"] == 15


def test_knn_config_from_json():
    config = KnnConfig.from_json(
        json.loads((FIXTURES_DIR / "knn_config.json").read_text(encoding="utf-8"))
    )

    assert config.k_neighbors == 3
    assert "post_drop_mean_motion" in config.stage1_feature_names
    assert config.stage1_model_path.name == "knn_stage1.joblib"
    assert config.stage2_model_path.name == "knn_stage2.joblib"


def test_trip_recorder_config_from_json():
    config = TripRecorderConfig.from_json(
        {
            "enabled": True,
            "segments_dir": "data/trips",
            "segment_seconds": 300,
            "ffmpeg_crf": 20,
        }
    )

    assert config.enabled is True
    assert config.segments_dir == Path("data/trips")
    assert config.logs_dir == Path("src/main/data/logs")
    assert config.stats_interval_s == 15.0
    assert config.segment_seconds == 300


def test_trip_recorder_config_logs_dir_override():
    config = TripRecorderConfig.from_json(
        {
            "enabled": True,
            "segments_dir": "data/trips",
            "logs_dir": "data/logs",
            "stats_interval_s": 30,
            "segment_seconds": 300,
            "ffmpeg_crf": 20,
        }
    )
    assert config.logs_dir == Path("data/logs")
    assert config.stats_interval_s == 30.0


def test_trip_recorder_config_defaults_disabled():
    config = TripRecorderConfig.from_json(
        {
            "segments_dir": "data/trips",
            "segment_seconds": 120,
            "ffmpeg_crf": 20,
        }
    )

    assert config.enabled is False


def test_trip_recorder_config_requires_positive_segment_seconds():
    with pytest.raises(ValueError, match="greater than 0"):
        TripRecorderConfig.from_json(
            {
                "enabled": True,
                "segments_dir": "data/trips",
                "segment_seconds": 0,
                "ffmpeg_crf": 20,
            }
        )


def test_recording_manager_config_rejects_negative_ffmpeg_crf():
    with pytest.raises(ValueError, match="ffmpeg_crf"):
        RecordingManagerConfig.from_json(
            {
                "clips_dir": "data/clips",
                "pre_roll_seconds": 10.0,
                "post_roll_seconds": 10.0,
                "coverage_tolerance": 0.95,
                "display": {"contrast": 1.0, "tone_enabled": False},
                "ffmpeg_crf": -1,
            }
        )


def test_recording_manager_config_recording_defaults():
    config = RecordingManagerConfig.from_json(
        {
            "clips_dir": "data/clips",
            "pre_roll_seconds": 10.0,
            "post_roll_seconds": 10.0,
            "coverage_tolerance": 0.95,
            "display": {"contrast": 1.0, "tone_enabled": False},
            "ffmpeg_crf": 20,
        }
    )

    assert config.record_safe_events is False


def test_recording_manager_config_requires_ffmpeg_crf():
    with pytest.raises(ValueError, match="ffmpeg_crf"):
        RecordingManagerConfig.from_json(
            {
                "clips_dir": "data/clips",
                "pre_roll_seconds": 10.0,
                "post_roll_seconds": 10.0,
                "coverage_tolerance": 0.95,
                "display": {"contrast": 1.0, "tone_enabled": False},
            }
        )


def test_buzzer_config_from_json():
    config = BuzzerConfig.from_json(
        {
            "gpio_pin": 18,
            "volume": 50,
            "pitch": 1000,
            "duration_seconds": 0.3,
            "play_on": {"unsafe": True, "safe": False},
        }
    )

    assert config.gpio_pin == 18
    assert config.volume == 50.0
    assert config.pitch == 1000.0
    assert config.duration_seconds == pytest.approx(0.3)
    assert config.play_on == BuzzerPlayOnConfig(unsafe=True, safe=False)
    assert config.enabled is True


def test_buzzer_config_disabled_when_both_play_on_false():
    config = BuzzerConfig.from_json(
        {
            "gpio_pin": 18,
            "volume": 50,
            "pitch": 1000,
            "duration_seconds": 0.3,
            "play_on": {"unsafe": False, "safe": False},
        }
    )

    assert config.enabled is False


def test_health_config_from_json():
    config = HealthConfig.from_json(
        {
            "render_wait_s": 90,
            "render_poll_s": 2,
            "render_request_timeout_s": 15,
            "internet_probe_host": "8.8.8.8",
            "internet_probe_port": 53,
            "internet_probe_timeout_s": 3,
            "public_https_host": "www.google.com",
            "public_https_port": 443,
            "wlan_interface": "wlan0",
            "keepalive_interval_s": 300,
            "keepalive_request_timeout_s": 15,
            "keepalive_fail_limit": 3,
            "log_path": "logs/health.log",
        }
    )

    assert config.render_wait_s == 90
    assert config.wlan_interface == "wlan0"
    assert config.keepalive_fail_limit == 3
    assert config.log_path == Path("logs/health.log")


def test_buzzer_config_rejects_invalid_volume():
    with pytest.raises(ValueError, match="volume"):
        BuzzerConfig.from_json(
            {
                "gpio_pin": 18,
                "volume": 150,
                "pitch": 1000,
                "duration_seconds": 0.3,
                "play_on": {"unsafe": True, "safe": False},
            }
        )


def test_fixture_files_parse_individually():
    camera = CameraConfig.from_json(json.loads((FIXTURES_DIR / "camera.json").read_text(encoding="utf-8")))
    preview = PreviewConfig.from_json(json.loads((FIXTURES_DIR / "preview.json").read_text(encoding="utf-8")))
    detector = DetectorConfig.from_json(json.loads((FIXTURES_DIR / "detector.json").read_text(encoding="utf-8")))
    event_manager = EventManagerConfig.from_json(
        json.loads((FIXTURES_DIR / "event_manager.json").read_text(encoding="utf-8"))
    )
    recording_manager = RecordingManagerConfig.from_json(
        json.loads((FIXTURES_DIR / "recording_manager.json").read_text(encoding="utf-8"))
    )
    trip_recorder = TripRecorderConfig.from_json(
        json.loads((FIXTURES_DIR / "trip_recorder.json").read_text(encoding="utf-8"))
    )
    buzzer = BuzzerConfig.from_json(json.loads((FIXTURES_DIR / "buzzer.json").read_text(encoding="utf-8")))

    assert camera.mode_id == "mjpeg_640x480_30"
    assert recording_manager.pre_roll_seconds == 10.0
    assert recording_manager.display.tone_enabled is True
    assert preview.window_name == "Test Preview"
    assert detector.allowed_classes == {"stop sign"}
    assert event_manager.trigger_labels == {"stop sign"}
    assert event_manager.area_history_seconds == 20.0
    assert recording_manager.record_safe_events is False
    assert trip_recorder.segment_seconds == 300
    assert buzzer.gpio_pin == 18
    assert buzzer.enabled is True


def test_trip_recorder_config_requires_ffmpeg_crf():
    with pytest.raises(ValueError, match="ffmpeg_crf"):
        TripRecorderConfig.from_json(
            {
                "enabled": True,
                "segments_dir": "data/trips",
                "segment_seconds": 300,
            }
        )
