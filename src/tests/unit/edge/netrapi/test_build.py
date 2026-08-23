from pathlib import Path
from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from config.loader import AppConfig
from netrapi.exceptions import DetectionError
from netrapi.build import NetraPiPipeline, build_pipeline
from netrapi.buzzer import Buzzer
from netrapi.detection import Detector
from netrapi.events import EventManager
from netrapi.recording import Recorder, RecordingManager, TripRecorder

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "config"
REPO_ROOT = Path(__file__).resolve().parents[5]


def _resolved_app_config() -> AppConfig:
    app_config = AppConfig.load(FIXTURES_DIR)
    return replace(
        app_config,
        knn=replace(
            app_config.knn,
            stage1_model_path=(REPO_ROOT / app_config.knn.stage1_model_path).resolve(),
            stage2_model_path=(REPO_ROOT / app_config.knn.stage2_model_path).resolve(),
        ),
    )


@patch.object(Detector, "load")
def test_build_pipeline_wires_components(mock_load):
    app_config = _resolved_app_config()

    pipeline = build_pipeline(app_config, verify_tpu=False, persist=False)

    mock_load.assert_called_once()
    assert isinstance(pipeline, NetraPiPipeline)
    assert pipeline.app_config is app_config
    assert isinstance(pipeline.manager, RecordingManager)
    assert isinstance(pipeline.manager.detector, Detector)
    assert isinstance(pipeline.manager.event_manager, EventManager)
    assert isinstance(pipeline.manager.recorder, Recorder)
    assert isinstance(pipeline.manager.trip_recorder, TripRecorder)
    assert isinstance(pipeline.manager.buzzer, Buzzer)
    assert pipeline.manager._local_store is None
    assert pipeline.manager.app_config.recording_manager == app_config.recording_manager
    assert pipeline.manager.buzzer.config == app_config.buzzer
    assert pipeline.manager.pre_buffer._recording_manager_config == app_config.recording_manager
    assert pipeline.manager.event_manager.config.trigger_labels == {"stop sign"}
    assert pipeline.manager.detector.config.input_dtype == "uint8"


@patch.object(Detector, "verify_tpu", return_value=False)
@patch.object(Detector, "load")
def test_build_pipeline_verify_tpu_failure_raises(mock_load, mock_verify_tpu):
    app_config = _resolved_app_config()

    with pytest.raises(DetectionError, match="TPU verification failed"):
        build_pipeline(app_config, verify_tpu=True, persist=False)

    mock_load.assert_called_once()
    mock_verify_tpu.assert_called_once()


@patch.object(Detector, "load")
def test_build_pipeline_persist_attaches_local_store(mock_load):
    app_config = _resolved_app_config()
    store = MagicMock()

    with (
        patch("netrapi.local_store.LocalStore", return_value=store),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=None),
    ):
        pipeline = build_pipeline(app_config, verify_tpu=False, persist=True)

    mock_load.assert_called_once()
    assert pipeline.manager._local_store is store
    assert pipeline.manager._cloud_ingest is None


@patch.object(Detector, "load")
def test_build_pipeline_persist_attaches_cloud_ingest(mock_load):
    app_config = _resolved_app_config()
    store = MagicMock()
    cloud = MagicMock()

    with (
        patch("netrapi.local_store.LocalStore", return_value=store),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=cloud),
    ):
        pipeline = build_pipeline(app_config, verify_tpu=False, persist=True)

    assert pipeline.manager._cloud_ingest is cloud


def test_pipeline_run_delegates_to_manager():
    app_config = _resolved_app_config()
    manager = MagicMock()
    pipeline = NetraPiPipeline(app_config=app_config, manager=manager)

    pipeline.run(max_laps=3)

    manager.run_loop.assert_called_once_with(max_laps=3)
