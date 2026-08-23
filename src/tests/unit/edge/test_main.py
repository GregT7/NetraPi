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

    assert not hasattr(args, "max_laps")
    assert args.full_record is None
    assert args.drain_trips is None
    assert args.delete_uploaded_local is False
    assert args.delete_all_local is False
    assert args.delete_after_drain is None


def test_parse_args_rejects_max_laps():
    from main import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--max-laps", "5"])


def test_parse_args_full_record():
    from main import parse_args

    args = parse_args(["--full-record"])
    assert args.full_record is True

    args = parse_args(["--no-full-record"])
    assert args.full_record is False


def test_main_runs_pipeline():
    from main import main
    from netrapi.health import HealthResult

    pipeline = MagicMock()
    health = HealthResult(mode="online", abort=False, detector=MagicMock())
    with (
        patch("config.loader.AppConfig.load", return_value=MagicMock()) as load_config,
        patch("db.database.init_engine") as init_engine,
        patch("netrapi.build_pipeline", return_value=pipeline) as build,
        patch("netrapi.backend_auth.apply_edge_env") as apply_env,
        patch("netrapi.health.run_boot_health", return_value=health),
        patch("netrapi.health.KeepAlive") as keepalive_cls,
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        keepalive_cls.return_value = MagicMock()
        exit_code = main(["--full-record"])

    assert exit_code == 0
    apply_env.assert_called_once_with()
    load_config.assert_called_once_with((EDGE_DIR / "config").resolve())
    init_engine.assert_called_once_with()
    build.assert_called_once()
    assert build.call_args.kwargs["cloud_enabled"] is True
    pipeline.run.assert_called_once_with(full_record=True)
    keepalive_cls.return_value.start.assert_called_once()
    keepalive_cls.return_value.stop.assert_called_once()


def test_main_drain_trips_skips_pipeline():
    from main import main

    ingest = MagicMock()
    ingest.drain_trip_segments.return_value = 2
    with (
        patch("netrapi.backend_auth.apply_edge_env") as apply_env,
        patch("db.database.init_engine") as init_engine,
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.health.wake_render", return_value=True),
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
    ):
        exit_code = main(["--drain-trips", "trips"])

    assert exit_code == 0
    apply_env.assert_called_once_with()
    init_engine.assert_called_once_with()
    ingest.drain_trip_segments.assert_called_once_with()
    build.assert_not_called()


def test_main_drain_trips_returns_1_without_auth():
    from main import main

    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=None),
        patch("netrapi.build_pipeline") as build,
    ):
        assert main(["--drain-trips", "trips"]) == 1
    build.assert_not_called()


def test_parse_args_maintenance_jobs_are_exclusive():
    from main import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--drain-trips", "trips", "--delete-uploaded-local"])


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


def test_main_tpu_abort_skips_pipeline():
    from main import main
    from netrapi.health import HealthResult

    health = HealthResult(mode="offline", abort=True, detector=None)
    with (
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch("db.database.init_engine"),
        patch("netrapi.build_pipeline") as build,
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("netrapi.health.run_boot_health", return_value=health),
        patch("netrapi.health.KeepAlive") as keepalive_cls,
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        assert main([]) == 1
    build.assert_not_called()
    keepalive_cls.assert_not_called()


def test_main_offline_skips_keepalive():
    from main import main
    from netrapi.health import HealthResult

    pipeline = MagicMock()
    health = HealthResult(mode="offline", abort=False, detector=MagicMock())
    with (
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch("db.database.init_engine"),
        patch("netrapi.build_pipeline", return_value=pipeline) as build,
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("netrapi.health.run_boot_health", return_value=health),
        patch("netrapi.health.KeepAlive") as keepalive_cls,
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        assert main([]) == 0
    assert build.call_args.kwargs["cloud_enabled"] is False
    keepalive_cls.assert_not_called()
    pipeline.run.assert_called_once()


def test_main_drain_clips():
    from main import main

    ingest = MagicMock()
    ingest.drain_clips.return_value = 3
    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.health.wake_render", return_value=True),
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
    ):
        assert main(["--drain-trips", "clips"]) == 0
    ingest.drain_clips.assert_called_once_with()
    ingest.drain_trip_segments.assert_not_called()
    build.assert_not_called()


def test_main_drain_both_clips_then_trips():
    from main import main

    ingest = MagicMock()
    ingest.drain_clips.return_value = 1
    ingest.drain_trip_segments.return_value = 2
    order: list[str] = []
    ingest.drain_clips.side_effect = lambda: order.append("clips") or 1
    ingest.drain_trip_segments.side_effect = lambda: order.append("trips") or 2
    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.health.wake_render", return_value=True),
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
    ):
        assert main(["--drain-trips", "both"]) == 0
    assert order == ["clips", "trips"]
    build.assert_not_called()


def test_main_drain_aborts_when_render_wake_fails():
    from main import main

    ingest = MagicMock()
    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.health.wake_render", return_value=False),
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
    ):
        assert main(["--drain-trips", "trips"]) == 1
    ingest.drain_clips.assert_not_called()
    ingest.drain_trip_segments.assert_not_called()
    build.assert_not_called()


def test_parse_args_drain_trips_requires_choice():
    from main import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--drain-trips"])
    args = parse_args(["--drain-trips", "clips"])
    assert args.drain_trips == "clips"


def test_parse_args_delete_after_drain_pairs_with_drain():
    from main import parse_args

    args = parse_args(["--drain-trips", "clips", "--delete-after-drain", "clips"])
    assert args.drain_trips == "clips"
    assert args.delete_after_drain == "clips"


def test_main_delete_after_drain_requires_drain_trips():
    from main import main

    assert main(["--delete-after-drain", "both"]) == 1


def test_main_drain_then_delete_after_drain():
    from main import main

    ingest = MagicMock()
    order: list[str] = []
    ingest.drain_clips.side_effect = lambda: order.append("clips") or 1
    ingest.drain_trip_segments.side_effect = lambda: order.append("trips") or 2
    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.health.wake_render", return_value=True),
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch(
            "netrapi.local_cleanup.delete_uploaded_local_media", return_value=3
        ) as cleanup,
    ):
        cleanup.side_effect = lambda *_a, **_k: order.append("delete") or 3
        assert main(["--drain-trips", "both", "--delete-after-drain", "clips"]) == 0
    assert order == ["clips", "trips", "delete"]
    cleanup.assert_called_once_with(ingest, target="clips")
    build.assert_not_called()


def test_main_drain_wake_fail_skips_delete_after_drain():
    from main import main

    ingest = MagicMock()
    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.init_engine"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.health.wake_render", return_value=False),
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch("netrapi.local_cleanup.delete_uploaded_local_media") as cleanup,
    ):
        assert main(["--drain-trips", "trips", "--delete-after-drain", "trips"]) == 1
    ingest.drain_clips.assert_not_called()
    ingest.drain_trip_segments.assert_not_called()
    cleanup.assert_not_called()
    build.assert_not_called()
