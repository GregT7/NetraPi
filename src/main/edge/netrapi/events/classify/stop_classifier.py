"""Two-stage kNN stop-sign classifier loaded from joblib pipelines."""

from __future__ import annotations

from pathlib import Path

import joblib

from config.types import KnnConfig
from netrapi.events.enums import Stage1Label, Stage2Label, StopSignEnum
from netrapi.exceptions import ClassificationError

_STAGE2_TO_ENUM = {
    Stage2Label.ROLLING_STOP: StopSignEnum.ROLLING_STOP,
    Stage2Label.RUN_THROUGH: StopSignEnum.RUN_THROUGH,
}


class StopClassifier:
    """Load stage-1 / stage-2 sklearn pipelines once; return StopSignEnum."""

    def __init__(self, config: KnnConfig) -> None:
        self._config = config
        if not config.stage1_model_path.is_file():
            raise FileNotFoundError(f"Missing stage-1 kNN model: {config.stage1_model_path}")
        if not config.stage2_model_path.is_file():
            raise FileNotFoundError(f"Missing stage-2 kNN model: {config.stage2_model_path}")
        self._stage1 = joblib.load(config.stage1_model_path)
        self._stage2 = joblib.load(config.stage2_model_path)

    @property
    def config(self) -> KnnConfig:
        return self._config

    @classmethod
    def from_paths(cls, stage1_path: Path, stage2_path: Path, *, k_neighbors: int = 3) -> StopClassifier:
        config = KnnConfig(
            k_neighbors=k_neighbors,
            stage1_feature_names=(
                "post_drop_mean_motion",
                "post_drop_min_motion",
                "post_drop_p95_motion",
                "post_drop_stop_fraction",
            ),
            stage2_feature_names=("post_drop_min_motion", "approach_area_sum_pct"),
            stage1_model_path=stage1_path,
            stage2_model_path=stage2_path,
        )
        return cls(config)

    def classify(self, stage1_features: list[float], stage2_features: list[float]) -> StopSignEnum:
        stage1_raw = str(self._stage1.predict([stage1_features])[0])
        try:
            stage1 = Stage1Label(stage1_raw)
        except ValueError as exc:
            raise ClassificationError(f"Unexpected stage-1 kNN label: {stage1_raw!r}") from exc

        if stage1 is Stage1Label.COMPLETE_STOP:
            return StopSignEnum.COMPLETE_STOP

        stage2_raw = str(self._stage2.predict([stage2_features])[0])
        try:
            stage2 = Stage2Label(stage2_raw)
        except ValueError as exc:
            raise ClassificationError(f"Unexpected stage-2 kNN label: {stage2_raw!r}") from exc
        return _STAGE2_TO_ENUM[stage2]
