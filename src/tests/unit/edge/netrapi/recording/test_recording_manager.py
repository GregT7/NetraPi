from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from config.loader import AppConfig
from config.types import (
    ApproachConfig,
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
    BuzzerConfig,
    BuzzerPlayOnConfig,
)
from netrapi.buffer import Classification, FrameBuffer, FrameRecord
from netrapi.events import DrivingEvent, StopSignEnum
from netrapi.recording import Recorder, RecordingManager


def _default_display(**overrides: float | bool) -> DisplayConfig:
    values: dict[str, float | bool] = {
        "contrast": 1.0,
        "tone_enabled": False,
        "tone_brightness": 10.0,
    }
    values.update(overrides)
    return DisplayConfig(
        contrast=float(values["contrast"]),
        tone_enabled=bool(values["tone_enabled"]),
        tone_brightness=float(values["tone_brightness"]),
    )


class _FakeCamera:
    def __init__(self, frame: np.ndarray, *, capture_fps: float = 30.0) -> None:
        self._frame = frame
        self.capture_fps = capture_fps

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def read(self) -> np.ndarray:
        return self._frame.copy()

    def measure_fps(self, *, apply: bool = False) -> float:
        if apply:
            self.capture_fps = 30.0
        return 30.0


def _app_config(
    tmp_path: Path,
    *,
    recording_manager: RecordingManagerConfig | None = None,
) -> AppConfig:
    return AppConfig(
        config_dir=tmp_path,
        camera=CameraConfig(
            device="/dev/video0",
            mode_id="test",
            width=64,
            height=48,
            ndim=3,
            channels=3,
            spec_fps=30.0,
            recommended_fps=30.0,
            input_format="mjpeg",
        ),
        preview=PreviewConfig(
            window_name="test",
            window_x=0,
            window_y=0,
            max_width=320,
            max_height=240,
            enabled=False,
            toggle_key="t",
        ),
        detector=DetectorConfig(
            model_path=Path("model.tflite"),
            labels_path=Path("labels.txt"),
            input_width=320,
            input_height=320,
            channels=3,
            input_dtype="uint8",
            score_threshold=0.5,
            top_k=5,
            allowed_classes={"stop sign"},
        ),
        event_manager=_default_event_manager_config(),
        approach=ApproachConfig.from_json(
            {
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
        ),
        motion=MotionConfig.from_json(
            {
                "motion_roi": {"x_min": 0.25, "x_max": 0.75, "y_min": 0.55, "y_max": 0.95},
                "flow_scale": 0.5,
                "motion_smoothing_window": 5,
                "stopped_motion_threshold": 0.6,
                "crawl_motion_threshold": 2.5,
                "post_drop_window_s": 5.0,
                "farneback": {
                    "pyr_scale": 0.5,
                    "levels": 3,
                    "winsize": 15,
                    "iterations": 3,
                    "poly_n": 5,
                    "poly_sigma": 1.2,
                },
            }
        ),
        knn=KnnConfig(
            k_neighbors=3,
            stage1_feature_names=(
                "post_drop_mean_motion",
                "post_drop_min_motion",
                "post_drop_p95_motion",
                "post_drop_stop_fraction",
            ),
            stage2_feature_names=("post_drop_min_motion", "approach_area_sum_pct"),
            stage1_model_path=Path("knn_stage1.joblib"),
            stage2_model_path=Path("knn_stage2.joblib"),
        ),
        recording_manager=recording_manager or _default_recording_manager_config(tmp_path),
        trip_recorder=TripRecorderConfig(
            enabled=False,
            segments_dir=tmp_path / "trips",
            segment_seconds=300,
            ffmpeg_crf=20,
        ),
        buzzer=BuzzerConfig(
            gpio_pin=18,
            volume=50.0,
            pitch=1000.0,
            duration_seconds=0.3,
            play_on=BuzzerPlayOnConfig(unsafe=True, safe=False),
        ),
        health=HealthConfig.from_json(
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
        ),
    )


def _default_event_manager_config(**overrides: object) -> EventManagerConfig:
    values: dict[str, object] = {
        "trigger_labels": {"stop sign"},
        "area_history_seconds": 20.0,
    }
    values.update(overrides)
    return EventManagerConfig(
        trigger_labels=set(values["trigger_labels"]),  # type: ignore[arg-type]
        area_history_seconds=float(values["area_history_seconds"]),  # type: ignore[arg-type]
    )


def _default_recording_manager_config(
    tmp_path: Path,
    *,
    pre_roll_seconds: float = 10.0,
    post_roll_seconds: float = 10.0,
    coverage_tolerance: float = 0.95,
    display: DisplayConfig | None = None,
    record_safe_events: bool = False,
    ffmpeg_crf: int = 20,
) -> RecordingManagerConfig:
    return RecordingManagerConfig(
        clips_dir=tmp_path / "clips",
        pre_roll_seconds=pre_roll_seconds,
        post_roll_seconds=post_roll_seconds,
        coverage_tolerance=coverage_tolerance,
        display=display or _default_display(),
        record_safe_events=record_safe_events,
        ffmpeg_crf=ffmpeg_crf,
    )


def _event_manager_mock(
    *,
    evaluate_return: DrivingEvent | None = None,
    needs_detection: bool = True,
    ready_to_evaluate: bool | None = None,
) -> MagicMock:
    event_manager = MagicMock()
    event_manager.evaluate.return_value = evaluate_return
    event_manager.needs_detection = needs_detection
    event_manager.observe.return_value = False
    event_manager.last_latched_approach = None
    if ready_to_evaluate is None:
        ready_to_evaluate = evaluate_return is not None
    event_manager.ready_to_evaluate = ready_to_evaluate
    return event_manager


def _default_event_manager() -> MagicMock:
    return _event_manager_mock()


def _default_detector() -> MagicMock:
    detector = MagicMock()
    detector.classify.return_value = []
    return detector


def _recording_manager(
    app_config: AppConfig,
    frame: np.ndarray,
    *,
    camera: _FakeCamera | None = None,
    preview: MagicMock | None = None,
    pre_buffer: FrameBuffer | None = None,
    post_buffer: FrameBuffer | None = None,
    detector: MagicMock | None = None,
    event_manager: MagicMock | None = None,
    recorder: Recorder | MagicMock | None = None,
    trip_recorder: MagicMock | None = None,
    buzzer: MagicMock | None = None,
    local_store=None,
    cloud_ingest=None,
) -> RecordingManager:
    config = app_config.recording_manager
    return RecordingManager(
        app_config,
        camera=camera or _FakeCamera(frame),
        preview=preview or MagicMock(enabled=False),
        pre_buffer=pre_buffer or FrameBuffer(config),
        post_buffer=post_buffer or FrameBuffer(),
        detector=detector or _default_detector(),
        event_manager=event_manager or _default_event_manager(),
        recorder=recorder or Recorder(config),
        trip_recorder=trip_recorder
        or MagicMock(
            enabled=False,
            is_started=False,
            config=app_config.trip_recorder,
        ),
        buzzer=buzzer or MagicMock(),
        local_store=local_store,
        cloud_ingest=cloud_ingest,
    )


def test_idle_lap_pushes_pre_buffer(tmp_path: Path):
    frame = np.full((48, 64, 3), 5, dtype=np.uint8)
    app_config = _app_config(tmp_path)
    manager = _recording_manager(app_config, frame)

    manager.run_one_lap()

    assert manager.clip_active is False
    assert len(manager.pre_buffer) == 1
    assert manager.pre_buffer.latest().raw[0, 0, 0] == 5


def test_idle_lap_patches_classifications_from_detector(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    detector = MagicMock()
    detector.classify.return_value = [
        Classification("stop sign", 0.88, (0.0, 0.0, 1.0, 1.0)),
    ]
    manager = _recording_manager(
        _app_config(tmp_path),
        frame,
        detector=detector,
    )

    manager.run_one_lap()

    detector.classify.assert_called_once()
    assert manager.pre_buffer.latest().classifications[0].label == "stop sign"
    assert manager.pre_buffer.latest().classifications[0].score == pytest.approx(0.88)


def test_idle_lap_skips_detector_when_collect_post_drop(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    detector = MagicMock()
    detector.classify.return_value = [
        Classification("stop sign", 0.88, (0.0, 0.0, 1.0, 1.0)),
    ]
    event_manager = _event_manager_mock(needs_detection=False)
    manager = _recording_manager(
        _app_config(tmp_path),
        frame,
        detector=detector,
        event_manager=event_manager,
    )

    manager.run_one_lap()

    detector.classify.assert_not_called()
    event_manager.observe.assert_called_once()
    event_manager.evaluate.assert_not_called()
    assert manager.pre_buffer.latest().classifications == []
    assert manager.clip_active is False


def test_complete_stop_does_not_start_clip(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    event_manager = _event_manager_mock(
        evaluate_return=DrivingEvent(type=StopSignEnum.COMPLETE_STOP),
    )
    manager = _recording_manager(
        _app_config(tmp_path, recording_manager=_default_recording_manager_config(tmp_path, post_roll_seconds=0.0)),
        frame,
        event_manager=event_manager,
    )

    manager.run_one_lap()

    assert manager.clip_active is False
    assert len(manager.post_buffer) == 0


def test_unsafe_stop_sign_starts_clip_collection(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    event = DrivingEvent(type=StopSignEnum.ROLLING_STOP)
    event_manager = _event_manager_mock(evaluate_return=event)
    buzzer = MagicMock()
    manager = _recording_manager(
        _app_config(tmp_path, recording_manager=_default_recording_manager_config(tmp_path, post_roll_seconds=0.0)),
        frame,
        event_manager=event_manager,
        buzzer=buzzer,
    )

    manager.run_one_lap()

    assert manager.clip_active is True
    assert len(manager.post_buffer) == 0
    buzzer.beep.assert_called_once_with(event)


def test_complete_stop_beeps_even_when_clip_not_started(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    event = DrivingEvent(type=StopSignEnum.COMPLETE_STOP)
    event_manager = _event_manager_mock(evaluate_return=event)
    buzzer = MagicMock()
    manager = _recording_manager(
        _app_config(tmp_path),
        frame,
        event_manager=event_manager,
        buzzer=buzzer,
    )

    manager.run_one_lap()

    assert manager.clip_active is False
    buzzer.beep.assert_called_once_with(event)


def test_complete_stop_starts_clip_when_safe_recording_enabled(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    event_manager = _event_manager_mock(
        evaluate_return=DrivingEvent(type=StopSignEnum.COMPLETE_STOP),
    )
    manager = _recording_manager(
        _app_config(
            tmp_path,
            recording_manager=_default_recording_manager_config(
                tmp_path,
                post_roll_seconds=0.0,
                record_safe_events=True,
            ),
        ),
        frame,
        event_manager=event_manager,
    )

    manager.run_one_lap()

    assert manager.clip_active is True


def test_unsafe_stop_sign_always_starts_clip_even_when_safe_recording_disabled(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    event_manager = _event_manager_mock(
        evaluate_return=DrivingEvent(type=StopSignEnum.ROLLING_STOP),
    )
    manager = _recording_manager(
        _app_config(
            tmp_path,
            recording_manager=_default_recording_manager_config(
                tmp_path,
                post_roll_seconds=0.0,
                record_safe_events=False,
            ),
        ),
        frame,
        event_manager=event_manager,
    )

    manager.run_one_lap()

    assert manager.clip_active is True


def test_post_roll_completes_and_writes_clip(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    config = _default_recording_manager_config(tmp_path, pre_roll_seconds=0.1, post_roll_seconds=0.0)
    app_config = _app_config(tmp_path, recording_manager=config)
    built_recorder = Recorder(config)
    built_recorder.write_clip = MagicMock(
        return_value=MagicMock(
            clip_path=tmp_path / "clips" / "clip_1.mp4",
            pre_frame_count=1,
            post_frame_count=1,
            pre_ok=True,
            post_ok=True,
            notes="",
        )
    )
    manager = _recording_manager(app_config, frame, recorder=built_recorder)

    manager.pre_buffer.push(FrameRecord(raw=frame, display=frame), captured_at=0.0)
    manager.begin_clip()
    result = manager.run_one_lap()

    assert result is not None
    assert manager.clip_active is False
    assert len(manager.pre_buffer) == 0
    assert len(manager.post_buffer) == 0
    built_recorder.write_clip.assert_called_once()


def test_capture_frame_record_builds_raw_and_display(tmp_path: Path):
    frame = np.ones((48, 64, 3), dtype=np.uint8) * 40
    manager = _recording_manager(_app_config(tmp_path), frame)

    record = manager._capture_frame_record()

    assert record.raw[0, 0, 0] == 40
    assert record.display[0, 0, 0] == 40
    assert record.display is not record.raw


def test_prepare_display_applies_contrast_with_mocked_cv2(tmp_path: Path):
    frame = np.ones((48, 64, 3), dtype=np.uint8) * 40
    manager = _recording_manager(
        _app_config(
            tmp_path,
            recording_manager=_default_recording_manager_config(tmp_path, display=_default_display(contrast=1.5)),
        ),
        frame,
    )
    processed = np.ones((48, 64, 3), dtype=np.uint8) * 60

    mock_cv2 = MagicMock()
    mock_cv2.addWeighted.return_value = processed

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        record = manager._capture_frame_record()

    assert record.display is processed
    mock_cv2.addWeighted.assert_called_once()


def test_run_one_lap_full_record_writes_trip_frame(tmp_path: Path):
    frame = np.ones((48, 64, 3), dtype=np.uint8) * 25
    trip_recorder = MagicMock(enabled=True, is_started=False, config=MagicMock(segment_seconds=300))
    manager = _recording_manager(_app_config(tmp_path), frame, trip_recorder=trip_recorder)

    manager.run_one_lap(full_record=True)

    trip_recorder.start.assert_called_once_with(frame_shape=frame.shape)
    trip_recorder.append_frame.assert_called_once()


def test_run_loop_stops_trip_recorder(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    trip_recorder = MagicMock(enabled=False, is_started=False, config=MagicMock(segment_seconds=300))
    buzzer = MagicMock()
    manager = _recording_manager(_app_config(tmp_path), frame, trip_recorder=trip_recorder, buzzer=buzzer)

    manager.run_loop(max_laps=1)

    trip_recorder.stop.assert_called_once()
    buzzer.open.assert_called_once()
    buzzer.close.assert_called_once()


def test_run_loop_starts_and_ends_driving_session(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    store = MagicMock()
    store.start_session.return_value = 7
    store.ensure_config_snapshot.return_value = 1
    manager = _recording_manager(_app_config(tmp_path), frame, local_store=store)

    manager.run_loop(max_laps=0)

    store.ensure_config_snapshot.assert_called_once()
    store.start_session.assert_called_once()
    assert store.start_session.call_args.kwargs["master_config_id"] == 1
    store.end_session.assert_called_once()
    assert store.end_session.call_args.args[0] == 7


def test_run_loop_syncs_session_to_cloud(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    store = MagicMock()
    store.start_session.return_value = 7
    store.ensure_config_snapshot.return_value = 1
    cloud = MagicMock()
    manager = _recording_manager(
        _app_config(tmp_path), frame, local_store=store, cloud_ingest=cloud
    )

    manager.run_loop(max_laps=0)

    cloud.sync_master_config.assert_called_with(1)
    assert cloud.sync_session.call_count == 2
    cloud.sync_session.assert_any_call(7)


def test_run_loop_cloud_failure_does_not_abort(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    store = MagicMock()
    store.start_session.return_value = 7
    store.ensure_config_snapshot.return_value = 1
    cloud = MagicMock()
    cloud.sync_session.side_effect = RuntimeError("backend down")
    manager = _recording_manager(
        _app_config(tmp_path), frame, local_store=store, cloud_ingest=cloud
    )

    manager.run_loop(max_laps=0)

    store.end_session.assert_called_once()


def test_finish_clip_attaches_clip_and_syncs(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    config = _default_recording_manager_config(
        tmp_path, pre_roll_seconds=0.1, post_roll_seconds=0.0
    )
    app_config = _app_config(tmp_path, recording_manager=config)
    built_recorder = Recorder(config)
    built_recorder.write_clip = MagicMock(
        return_value=MagicMock(
            clip_path=tmp_path / "clips" / "clip_1.mp4",
            pre_frame_count=1,
            post_frame_count=1,
            pre_ok=True,
            post_ok=True,
            notes="",
        )
    )
    store = MagicMock()
    store.attach_clip.return_value = 99
    cloud = MagicMock()
    manager = _recording_manager(
        app_config,
        frame,
        recorder=built_recorder,
        local_store=store,
        cloud_ingest=cloud,
    )
    manager._driving_session_id = 7
    manager._pending_event_id = 42
    manager.pre_buffer.push(FrameRecord(raw=frame, display=frame), captured_at=0.0)
    manager.begin_clip()
    manager.run_one_lap()

    store.attach_clip.assert_called_once()
    assert store.attach_clip.call_args.args[0] == 42
    assert manager.flush_ingest(timeout_s=5.0)
    cloud.sync_event.assert_called_once_with(42)


def test_commit_evaluated_event_persists_metadata_without_clip(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    store = MagicMock()
    store.persist_event.return_value = 11
    cloud = MagicMock()
    manager = _recording_manager(
        _app_config(tmp_path), frame, local_store=store, cloud_ingest=cloud
    )
    manager._driving_session_id = 7
    event = DrivingEvent(type=StopSignEnum.COMPLETE_STOP)

    manager._commit_evaluated_event(event)

    store.persist_event.assert_called_once()
    kwargs = store.persist_event.call_args.kwargs
    assert kwargs["type_value"] == StopSignEnum.COMPLETE_STOP.model_label
    assert kwargs.get("clip_path") is None
    assert manager.flush_ingest(timeout_s=5.0)
    cloud.sync_event.assert_called_once_with(11)
    assert manager._pending_event_id == 11


def test_safe_event_commits_without_begin_clip(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    store = MagicMock()
    store.persist_event.return_value = 3
    cloud = MagicMock()
    event_manager = _event_manager_mock(
        evaluate_return=DrivingEvent(type=StopSignEnum.COMPLETE_STOP),
        needs_detection=False,
        ready_to_evaluate=True,
    )
    manager = _recording_manager(
        _app_config(tmp_path),
        frame,
        event_manager=event_manager,
        local_store=store,
        cloud_ingest=cloud,
    )
    manager._driving_session_id = 7

    result = manager.run_one_lap()

    assert result is None
    assert manager.clip_active is False
    store.persist_event.assert_called_once()
    store.attach_clip.assert_not_called()
    assert manager.flush_ingest(timeout_s=5.0)
    cloud.sync_event.assert_called_once_with(3)
    assert manager._pending_event_id is None


def test_unsafe_event_begins_clip_before_beep(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    store = MagicMock()
    store.persist_event.return_value = 5
    cloud = MagicMock()
    buzzer = MagicMock()
    event_manager = _event_manager_mock(
        evaluate_return=DrivingEvent(type=StopSignEnum.RUN_THROUGH),
        needs_detection=False,
        ready_to_evaluate=True,
    )
    order: list[str] = []
    manager = _recording_manager(
        _app_config(tmp_path),
        frame,
        event_manager=event_manager,
        local_store=store,
        cloud_ingest=cloud,
        buzzer=buzzer,
    )
    manager._driving_session_id = 7
    original_begin = manager.begin_clip

    def _begin_and_track() -> None:
        order.append("begin_clip")
        original_begin()

    buzzer.beep.side_effect = lambda _event: order.append("beep")
    with patch.object(manager, "begin_clip", side_effect=_begin_and_track):
        manager.run_one_lap()

    assert order[:2] == ["begin_clip", "beep"]
    assert manager.clip_active is True
    assert manager.flush_ingest(timeout_s=5.0)
    cloud.sync_event.assert_called_once_with(5)


def test_run_loop_closes_buzzer_when_lap_raises(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    buzzer = MagicMock()
    manager = _recording_manager(_app_config(tmp_path), frame, buzzer=buzzer)

    with patch.object(manager, "run_one_lap", side_effect=RuntimeError("lap failed")):
        with pytest.raises(RuntimeError, match="lap failed"):
            manager.run_loop(max_laps=1)

    buzzer.open.assert_called_once()
    buzzer.close.assert_called_once()
