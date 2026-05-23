from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from config.types import KnnConfig
from netrapi.events.enums import Stage1Label, Stage2Label, StopSignEnum
from netrapi.events.classify import StopClassifier
from netrapi.exceptions import ClassificationError

MODELS_DIR = Path(__file__).resolve().parents[5] / "main" / "edge" / "models"


def _knn_config() -> KnnConfig:
    return KnnConfig(
        k_neighbors=3,
        stage1_feature_names=(
            "post_drop_mean_motion",
            "post_drop_min_motion",
            "post_drop_p95_motion",
            "post_drop_stop_fraction",
        ),
        stage2_feature_names=("post_drop_min_motion", "approach_area_sum_pct"),
        stage1_model_path=MODELS_DIR / "knn_stage1.joblib",
        stage2_model_path=MODELS_DIR / "knn_stage2.joblib",
    )


def test_classify_maps_stage1_complete_stop():
    classifier = StopClassifier.__new__(StopClassifier)
    classifier._config = _knn_config()
    classifier._stage1 = MagicMock()
    classifier._stage1.predict.return_value = [Stage1Label.COMPLETE_STOP.value]
    classifier._stage2 = MagicMock()

    result = classifier.classify([0.0] * 4, [0.0] * 2)

    assert result is StopSignEnum.COMPLETE_STOP
    assert result.is_unsafe is False
    classifier._stage2.predict.assert_not_called()


def test_classify_maps_stage2_unsafe_subtypes():
    classifier = StopClassifier.__new__(StopClassifier)
    classifier._config = _knn_config()
    classifier._stage1 = MagicMock()
    classifier._stage1.predict.return_value = [Stage1Label.ROLLING_OR_RUN_THROUGH.value]
    classifier._stage2 = MagicMock()

    classifier._stage2.predict.return_value = [Stage2Label.ROLLING_STOP.value]
    rolling = classifier.classify([0.0] * 4, [0.0] * 2)
    assert rolling is StopSignEnum.ROLLING_STOP
    assert rolling.is_unsafe is True

    classifier._stage2.predict.return_value = [Stage2Label.RUN_THROUGH.value]
    run_through = classifier.classify([0.0] * 4, [0.0] * 2)
    assert run_through is StopSignEnum.RUN_THROUGH
    assert run_through.is_unsafe is True


def test_classify_unknown_stage1_label_raises():
    classifier = StopClassifier.__new__(StopClassifier)
    classifier._config = _knn_config()
    classifier._stage1 = MagicMock()
    classifier._stage2 = MagicMock()
    classifier._stage1.predict.return_value = ["unrelated"]

    with pytest.raises(ClassificationError, match="stage-1"):
        classifier.classify([0.0] * 4, [0.0] * 2)
    classifier._stage2.predict.assert_not_called()


def test_classify_unknown_stage2_label_raises():
    classifier = StopClassifier.__new__(StopClassifier)
    classifier._config = _knn_config()
    classifier._stage1 = MagicMock()
    classifier._stage2 = MagicMock()
    classifier._stage1.predict.return_value = [Stage1Label.ROLLING_OR_RUN_THROUGH.value]
    classifier._stage2.predict.return_value = ["complete-stop"]

    with pytest.raises(ClassificationError, match="stage-2"):
        classifier.classify([0.0] * 4, [0.0] * 2)


def test_stop_classifier_loads_joblibs_and_predicts():
    classifier = StopClassifier(_knn_config())
    stage1 = [0.2, 0.05, 0.4, 0.95]
    stage2 = [0.05, 10.0]
    result = classifier.classify(stage1, stage2)
    assert result in {
        StopSignEnum.COMPLETE_STOP,
        StopSignEnum.ROLLING_STOP,
        StopSignEnum.RUN_THROUGH,
    }


def test_stop_classifier_missing_model_raises(tmp_path: Path):
    config = KnnConfig(
        k_neighbors=3,
        stage1_feature_names=("a", "b", "c", "d"),
        stage2_feature_names=("a", "b"),
        stage1_model_path=tmp_path / "missing1.joblib",
        stage2_model_path=tmp_path / "missing2.joblib",
    )
    with pytest.raises(FileNotFoundError, match="stage-1"):
        StopClassifier(config)
