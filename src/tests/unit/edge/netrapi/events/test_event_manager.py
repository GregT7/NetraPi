from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from config.loader import AppConfig
from config.types import RecordingManagerConfig
from netrapi.buffer import Classification, FrameBuffer, FrameRecord
from netrapi.events import DrivingEvent, EventManager, StopSignEnum
from netrapi.events.enums import EventPhase
from netrapi.events.classify import StopClassifier
from netrapi.exceptions import EventError

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "fixtures" / "config"
MODELS_DIR = Path(__file__).resolve().parents[5] / "main" / "edge" / "models"


def _recording_config(tmp_path: Path) -> RecordingManagerConfig:
    return RecordingManagerConfig(
        clips_dir=tmp_path / "clips",
        pre_roll_seconds=10.0,
        post_roll_seconds=10.0,
        coverage_tolerance=0.95,
        display=AppConfig.load(FIXTURES_DIR).recording_manager.display,
        record_safe_events=False,
        ffmpeg_crf=23,
    )


def _manager() -> EventManager:
    app = AppConfig.load(FIXTURES_DIR)
    knn = replace(
        app.knn,
        stage1_model_path=MODELS_DIR / "knn_stage1.joblib",
        stage2_model_path=MODELS_DIR / "knn_stage2.joblib",
    )
    return EventManager(
        app.event_manager,
        approach=app.approach,
        motion=app.motion,
        classifier=StopClassifier(knn),
        fallback_fps=app.camera.recommended_fps,
    )


def _frame(*, area: float = 0.0, seed: int = 0) -> FrameRecord:
    rng = np.random.default_rng(seed)
    raw = rng.integers(0, 40, size=(48, 64, 3), dtype=np.uint8)
    classifications: list[Classification] = []
    if area > 0:
        side = area**0.5
        classifications = [
            Classification(
                label="stop sign",
                score=0.9,
                box=(0.1, 0.1, 0.1 + side, 0.1 + side),
            )
        ]
    return FrameRecord(raw=raw, classifications=classifications)


def test_watching_without_pattern_stays_not_ready(tmp_path: Path):
    manager = _manager()
    buffer = FrameBuffer(_recording_config(tmp_path))
    for index in range(5):
        buffer.push(_frame(area=0.0, seed=index), captured_at=float(index))
        manager.observe(buffer, now=float(index))
        assert manager.ready_to_evaluate is False
    assert manager.phase_name == "WATCHING"
    assert manager.needs_detection is True


def test_evaluate_when_not_ready_raises():
    manager = _manager()
    with pytest.raises(EventError, match="before ready_to_evaluate"):
        manager.evaluate()


def test_needs_detection_false_while_collect_post_drop():
    manager = _manager()
    assert manager.needs_detection is True
    manager._phase = EventPhase.COLLECT_POST_DROP
    assert manager.needs_detection is False
    manager.reset()
    assert manager.needs_detection is True


def test_forced_latch_then_window_elapse_emits(tmp_path: Path):
    manager = _manager()
    manager._motion = replace(manager._motion, post_drop_window_s=0.2)
    buffer = FrameBuffer(_recording_config(tmp_path))

    t0 = 10.0
    latch_frame = _frame(area=0.01, seed=1)
    manager._areas_snapshot = [0.001 * (1.25**i) for i in range(20)] + [0.001, 0.0]
    manager._detect_frame = len(manager._areas_snapshot) - 1
    manager._anchor_t = t0
    manager._latch_fps = 10.0
    manager._motion_tracker.prime(latch_frame.raw)
    manager._phase = EventPhase.COLLECT_POST_DROP

    buffer.push(latch_frame, captured_at=t0)
    manager.observe(buffer, now=t0 + 0.05)
    assert manager.ready_to_evaluate is False
    assert manager.phase_name == "COLLECT_POST_DROP"
    assert manager.needs_detection is False

    manager._classifier = MagicMock()
    manager._classifier.classify.return_value = StopSignEnum.COMPLETE_STOP

    moved = _frame(area=0.0, seed=2)
    moved.raw[20:40, 10:50] = 200
    buffer.push(moved, captured_at=t0 + 0.25)
    manager.observe(buffer, now=t0 + 0.25)
    assert manager.ready_to_evaluate is True

    event = manager.evaluate()

    assert isinstance(event, DrivingEvent)
    assert event.type is StopSignEnum.COMPLETE_STOP
    assert event.knn_stage1 is not None
    assert len(event.knn_stage1) == 4
    assert event.knn_stage2 is not None
    assert len(event.knn_stage2) == 2
    assert manager.phase_name == "WATCHING"
    assert manager.ready_to_evaluate is False


def test_evaluate_feature_failure_resets_and_raises(tmp_path: Path):
    manager = _manager()
    manager._ready_to_evaluate = True
    manager._anchor_t = 10.0
    manager._areas_snapshot = [0.1]
    manager._detect_frame = 0
    manager._latch_fps = 10.0
    manager._motion_history = []
    manager._phase = EventPhase.COLLECT_POST_DROP

    with pytest.raises(EventError, match="stage-1 feature extraction failed"):
        manager.evaluate()

    assert manager.phase_name == "WATCHING"
    assert manager.ready_to_evaluate is False
    assert manager._anchor_t is None


def test_reset_clears_collect_state():
    manager = _manager()
    manager._phase = EventPhase.COLLECT_POST_DROP
    manager._anchor_t = 1.0
    manager._areas_snapshot = [0.1]
    manager._motion_history = [(1.0, 0.5)]
    manager._ready_to_evaluate = True
    manager.reset()
    assert manager.phase_name == "WATCHING"
    assert manager._anchor_t is None
    assert manager._areas_snapshot == []
    assert manager._motion_history == []
    assert manager.ready_to_evaluate is False
