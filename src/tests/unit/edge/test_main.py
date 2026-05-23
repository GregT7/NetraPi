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
        patch("netrapi.build_pipeline", return_value=pipeline) as build,
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        exit_code = main(["--no-verify-tpu", "--max-laps", "2", "--full-record"])

    assert exit_code == 0
    load_config.assert_called_once_with((EDGE_DIR / "config").resolve())
    build.assert_called_once()
    assert build.call_args.kwargs["verify_tpu"] is False
    pipeline.run.assert_called_once_with(max_laps=2, full_record=True)


def test_main_returns_1_on_config_error():
    from config.loader import ConfigError
    from main import main

    with patch("config.loader.AppConfig.load", side_effect=ConfigError("broken")):
        assert main([]) == 1
