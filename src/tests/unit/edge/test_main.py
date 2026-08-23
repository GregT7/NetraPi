from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

EDGE_DIR = Path(__file__).resolve().parents[3] / "main" / "edge"
REPO_ROOT = EDGE_DIR.parents[2]


def test_resolve_runtime_paths_from_repo_relative():
    from config.loader import AppConfig
    from main import _resolve_runtime_paths

    app_config = AppConfig.load(EDGE_DIR / "config")
    resolved = _resolve_runtime_paths(app_config, REPO_ROOT)

    assert resolved.detector.model_path == (REPO_ROOT / "src/main/edge/models/ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite").resolve()
    assert resolved.detector.labels_path.is_file()
    assert resolved.knn.stage1_model_path == (REPO_ROOT / "src/main/edge/models/knn_stage1.joblib").resolve()
    assert resolved.knn.stage2_model_path == (REPO_ROOT / "src/main/edge/models/knn_stage2.joblib").resolve()
    assert resolved.knn.stage1_model_path.is_file()
    assert resolved.recording_manager.clips_dir == (REPO_ROOT / "src/main/data/clips").resolve()
    assert resolved.trip_recorder.segments_dir == (REPO_ROOT / "src/main/data/trips").resolve()


def test_parse_args_defaults():
    from main import parse_args

    args = parse_args([])

    assert args.verify_tpu is True
    assert args.max_laps is None
    assert args.full_record is None
    assert args.drain_trips is False
    assert args.delete_uploaded_local is False
    assert args.delete_all_local is False


def test_parse_args_max_laps():
    from main import parse_args

    args = parse_args(["--max-laps", "5", "--no-verify-tpu"])

    assert args.max_laps == 5
    assert args.verify_tpu is False


def test_parse_args_full_record():
    from main import parse_args

    args = parse_args(["--full-record"])
    assert args.full_record is True

    args = parse_args(["--no-full-record"])
    assert args.full_record is False


def test_main_runs_pipeline():
    from main import main

    pipeline = MagicMock()
    with (
        patch("config.loader.AppConfig.load", return_value=MagicMock()) as load_config,
        patch("db.database.init_engine") as init_engine,
        patch("netrapi.build_pipeline", return_value=pipeline) as build,
        patch("netrapi.backend_auth.apply_edge_env") as apply_env,
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        exit_code = main(["--no-verify-tpu", "--max-laps", "2", "--full-record"])

    assert exit_code == 0
    apply_env.assert_called_once_with()
    load_config.assert_called_once_with((EDGE_DIR / "config").resolve())
    init_engine.assert_called_once_with()
    build.assert_called_once()
    assert build.call_args.kwargs["verify_tpu"] is False
    pipeline.run.assert_called_once_with(max_laps=2, full_record=True)


def test_main_drain_trips_skips_pipeline():
    from main import main

    ingest = MagicMock()
    ingest.drain_trip_segments.return_value = 2
    with (
        patch("netrapi.backend_auth.apply_edge_env") as apply_env,
        patch("db.database.init_engine") as init_engine,
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load") as load_config,
    ):
        exit_code = main(["--drain-trips"])

    assert exit_code == 0
    apply_env.assert_called_once_with()
    init_engine.assert_called_once_with()
    ingest.drain_trip_segments.assert_called_once_with()
    build.assert_not_called()
    load_config.assert_not_called()


def test_main_drain_trips_returns_1_without_auth():
    from main import main

    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=None),
        patch("netrapi.build_pipeline") as build,
    ):
        assert main(["--drain-trips"]) == 1
    build.assert_not_called()


def test_parse_args_maintenance_jobs_are_exclusive():
    from main import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--drain-trips", "--delete-uploaded-local"])


def test_main_delete_uploaded_local_skips_pipeline():
    from main import main

    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest") as try_ingest,
        patch(
            "netrapi.local_cleanup.delete_uploaded_local_media", return_value=3
        ) as cleanup,
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load") as load_config,
    ):
        ingest = MagicMock()
        try_ingest.return_value = ingest
        assert main(["--delete-uploaded-local"]) == 0
    cleanup.assert_called_once_with(ingest)
    build.assert_not_called()
    load_config.assert_not_called()


def test_main_delete_all_local_skips_pipeline():
    from main import main

    app_config = MagicMock()
    app_config.recording_manager.clips_dir = Path("/clips")
    app_config.trip_recorder.segments_dir = Path("/trips")
    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest") as try_ingest,
        patch("netrapi.local_cleanup.delete_all_local_media", return_value=4) as cleanup,
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load", return_value=app_config),
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        ingest = MagicMock()
        try_ingest.return_value = ingest
        assert main(["--delete-all-local"]) == 0
    cleanup.assert_called_once_with(
        ingest, clips_dir=Path("/clips"), trips_dir=Path("/trips")
    )
    build.assert_not_called()


def test_main_returns_1_on_config_error():
    from config.loader import ConfigError
    from main import main

    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("config.loader.AppConfig.load", side_effect=ConfigError("broken")),
    ):
        assert main([]) == 1
