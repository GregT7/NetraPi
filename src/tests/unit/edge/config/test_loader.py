import json
from pathlib import Path

import pytest

from config.loader import AppConfig, ConfigError, load_json

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "config"
PRODUCTION_CONFIG_DIR = Path(__file__).resolve().parents[4] / "main" / "edge" / "config"


def test_load_json_reads_valid_file(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text('{"value": 1}', encoding="utf-8")

    assert load_json(path) == {"value": 1}


def test_load_json_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="Config file not found"):
        load_json(tmp_path / "missing.json")


def test_load_json_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_json(path)


def test_load_json_non_object_root(tmp_path):
    path = tmp_path / "array.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ConfigError, match="must be a JSON object"):
        load_json(path)


def test_app_config_loads_fixture_directory():
    app_config = AppConfig.load(FIXTURES_DIR)

    assert app_config.config_dir == FIXTURES_DIR.resolve()
    assert app_config.camera.device == "/dev/video0"
    assert app_config.camera.recommended_fps == 29.5
    assert app_config.recording_manager.clips_dir.name == "clips"
    assert app_config.recording_manager.coverage_tolerance == pytest.approx(0.95)
    assert app_config.recording_manager.display.contrast == 1.2
    assert app_config.recording_manager.display.tone_enabled is True
    assert app_config.preview.window_name == "Test Preview"
    assert app_config.detector.top_k == 5
    assert app_config.event_manager.trigger_labels == {"stop sign"}
    assert app_config.event_manager.area_history_seconds == 20.0
    assert app_config.approach.min_peak_pct == 0.25
    assert app_config.motion.post_drop_window_s == 5.0
    assert app_config.motion.stopped_motion_threshold == 0.6
    assert app_config.knn.k_neighbors == 3
    assert app_config.knn.stage1_model_path.name == "knn_stage1.joblib"
    assert app_config.recording_manager.record_safe_events is False
    assert app_config.trip_recorder.segment_seconds == 300
    assert app_config.buzzer.gpio_pin == 18
    assert app_config.buzzer.play_on.unsafe is True
    assert app_config.buzzer.play_on.safe is False
    assert app_config.buzzer.enabled is True
    assert app_config.health.render_wait_s == 90
    assert app_config.health.wlan_interface == "wlan0"


def test_app_config_loads_production_directory():
    app_config = AppConfig.load(PRODUCTION_CONFIG_DIR)

    assert app_config.camera.mode_id == "mjpeg_640x480_30"
    assert app_config.recording_manager.pre_roll_seconds == 10.0
    assert app_config.detector.allowed_classes == {"stop sign"}
    assert app_config.event_manager.trigger_labels == {"stop sign"}
    assert app_config.event_manager.area_history_seconds == 20.0
    assert app_config.approach.min_peak_pct == 0.25
    assert app_config.motion.post_drop_window_s == 5.0
    assert app_config.knn.stage2_model_path.name == "knn_stage2.joblib"
    assert app_config.recording_manager.record_safe_events is False
    assert app_config.trip_recorder.segment_seconds == 300
    assert app_config.buzzer.gpio_pin == 18
    assert app_config.buzzer.duration_seconds == pytest.approx(0.3)


def test_app_config_missing_directory(tmp_path):
    with pytest.raises(ConfigError, match="Config directory not found"):
        AppConfig.load(tmp_path / "missing")


def test_app_config_missing_required_file(tmp_path):
    (tmp_path / "camera.json").write_text(
        json.dumps(
            {
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
                        "spec_fps": 30.0,
                        "recommended_fps": 30.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Config file not found"):
        AppConfig.load(tmp_path)


def test_app_config_invalid_camera_mode_id(tmp_path):
    for name in (
        "camera.json",
        "preview.json",
        "detector.json",
        "event_manager.json",
        "approach_config.json",
        "motion_config.json",
        "knn_config.json",
        "recording_manager.json",
        "trip_recorder.json",
        "buzzer.json",
        "health.json",
    ):
        (tmp_path / name).write_text((FIXTURES_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")

    camera = json.loads((tmp_path / "camera.json").read_text(encoding="utf-8"))
    camera["mode_id"] = "does_not_exist"
    (tmp_path / "camera.json").write_text(json.dumps(camera), encoding="utf-8")

    with pytest.raises(ConfigError, match="mode_id 'does_not_exist' not found"):
        AppConfig.load(tmp_path)
