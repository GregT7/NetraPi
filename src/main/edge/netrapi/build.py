from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.loader import AppConfig

from netrapi.buffer import FrameBuffer
from netrapi.buzzer import Buzzer
from netrapi.capture import Camera, PreviewUI
from netrapi.detection import Detector
from netrapi.events import EventManager
from netrapi.exceptions import DetectionError
from netrapi.recording import Recorder, TripRecorder
from netrapi.recording.recording_manager import RecordingManager


def build_detector(app_config: AppConfig, *, verify_tpu: bool) -> Detector:
    detector = Detector(app_config.detector)
    detector.load()
    if verify_tpu and not detector.verify_tpu():
        raise DetectionError("Edge TPU verification failed")
    return detector


def build_event_manager(app_config: AppConfig) -> EventManager:
    from netrapi.events.classify import StopClassifier

    classifier = StopClassifier(app_config.knn)
    return EventManager(
        app_config.event_manager,
        approach=app_config.approach,
        motion=app_config.motion,
        classifier=classifier,
        fallback_fps=app_config.camera.recommended_fps,
    )


def build_recorder(app_config: AppConfig) -> Recorder:
    return Recorder(app_config.recording_manager)


def build_trip_recorder(app_config: AppConfig) -> TripRecorder:
    return TripRecorder(app_config.trip_recorder)


def build_buzzer(app_config: AppConfig) -> Buzzer:
    return Buzzer(app_config.buzzer)


def build_recording_manager(
    app_config: AppConfig,
    *,
    detector: Detector,
    event_manager: EventManager,
    recorder: Recorder,
    trip_recorder: TripRecorder,
    buzzer: Buzzer,
) -> RecordingManager:
    config = app_config.recording_manager
    return RecordingManager(
        app_config,
        camera=Camera(app_config.camera),
        preview=PreviewUI(app_config.preview),
        pre_buffer=FrameBuffer(config),
        post_buffer=FrameBuffer(),
        detector=detector,
        event_manager=event_manager,
        recorder=recorder,
        trip_recorder=trip_recorder,
        buzzer=buzzer,
    )


@dataclass(frozen=True)
class NetraPiPipeline:
    """Wired capture → detect → event → record components for one run session."""

    app_config: AppConfig
    manager: RecordingManager

    def run(self, **kwargs: Any) -> None:
        self.manager.run_loop(**kwargs)


def build_pipeline(app_config: AppConfig, *, verify_tpu: bool) -> NetraPiPipeline:
    detector = build_detector(app_config, verify_tpu=verify_tpu)
    event_manager = build_event_manager(app_config)
    recorder = build_recorder(app_config)
    trip_recorder = build_trip_recorder(app_config)
    buzzer = build_buzzer(app_config)
    manager = build_recording_manager(
        app_config,
        detector=detector,
        event_manager=event_manager,
        recorder=recorder,
        trip_recorder=trip_recorder,
        buzzer=buzzer,
    )
    return NetraPiPipeline(app_config=app_config, manager=manager)
