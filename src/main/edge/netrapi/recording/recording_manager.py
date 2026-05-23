from __future__ import annotations

import signal
import time
from datetime import datetime
from typing import Callable

import numpy as np

from config.loader import AppConfig

from netrapi.buffer import FrameBuffer, FrameRecord
from netrapi.buzzer import Buzzer
from netrapi.capture import Camera, PreviewUI
from netrapi.detection import Detector
from netrapi.events import EventManager
from netrapi.recording.clip_package import ClipPackage
from netrapi.recording.clip_result import ClipResult
from netrapi.recording.util.encoding_fps import clip_encoding_fps
from netrapi.recording.recorder import Recorder
from netrapi.recording.trip_recorder import TripRecorder


class RecordingManager:
    def __init__(
        self,
        app_config: AppConfig,
        *,
        camera: Camera,
        preview: PreviewUI,
        pre_buffer: FrameBuffer,
        post_buffer: FrameBuffer,
        detector: Detector,
        event_manager: EventManager,
        recorder: Recorder,
        trip_recorder: TripRecorder,
        buzzer: Buzzer,
    ) -> None:
        self._app_config = app_config
        self._camera = camera
        self._preview = preview
        self.pre_buffer = pre_buffer
        self.post_buffer = post_buffer
        self._detector = detector
        self._event_manager = event_manager
        self._recorder = recorder
        self._trip_recorder = trip_recorder
        self._buzzer = buzzer

        self._clip_active = False
        self._running = False
        self._post_roll_started_at: float | None = None
        self._triggered_at: datetime | None = None
        self._event_index = 0

    @property
    def app_config(self) -> AppConfig:
        return self._app_config

    @property
    def detector(self) -> Detector:
        return self._detector

    @property
    def event_manager(self) -> EventManager:
        return self._event_manager

    @property
    def recorder(self) -> Recorder:
        return self._recorder

    @property
    def trip_recorder(self) -> TripRecorder:
        return self._trip_recorder

    @property
    def buzzer(self) -> Buzzer:
        return self._buzzer

    @property
    def clip_active(self) -> bool:
        return self._clip_active

    @property
    def camera(self) -> Camera:
        return self._camera

    def begin_clip(self) -> None:
        if self._clip_active:
            return

        self._event_index += 1
        self._clip_active = True
        self._triggered_at = datetime.now()
        self._post_roll_started_at = time.monotonic()
        self.post_buffer.clear()

    def run_loop(
        self,
        *,
        max_laps: int | None = None,
        should_stop: Callable[[], bool] | None = None,
        full_record: bool | None = None,
    ) -> None:
        self._running = True
        trip_enabled = self._trip_recorder.enabled if full_record is None else full_record
        previous_handler = signal.getsignal(signal.SIGINT)

        def _handle_sigint(signum, frame) -> None:
            self._running = False

        signal.signal(signal.SIGINT, _handle_sigint)
        self._camera.open()
        self._buzzer.open()
        try:
            laps = 0
            while self._running:
                if should_stop and should_stop():
                    break
                if max_laps is not None and laps >= max_laps:
                    break
                self.run_one_lap(full_record=trip_enabled)
                laps += 1
        finally:
            signal.signal(signal.SIGINT, previous_handler)
            self._buzzer.close()
            self._camera.close()
            self._recorder.release()
            self._trip_recorder.stop()

    def run_one_lap(self, *, full_record: bool = False) -> ClipResult | None:
        record = self._capture_frame_record()
        if full_record:
            if not self._trip_recorder.is_started:
                self._trip_recorder.start(frame_shape=record.display.shape)
            self._trip_recorder.append_frame(record.display)

        if self._preview.enabled:
            self._preview.show(record.display)

        if not self._clip_active:
            self.pre_buffer.push(record)
            # Detector only while EventManager is Watching. After approach latch
            # (CollectPostDrop), skip TPU inference — observe uses motion only.
            if self._event_manager.needs_detection:
                classifications = self._detector.classify(record.raw)
                self.pre_buffer.latest().patch_classifications(classifications)
            self._event_manager.observe(self.pre_buffer)
            if self._event_manager.ready_to_evaluate:
                event = self._event_manager.evaluate()
                self._buzzer.beep(event)
                if event.is_unsafe or self._app_config.recording_manager.record_safe_events:
                    self.begin_clip()
            return None
        else:
            self.post_buffer.append(record)
            if self._post_roll_complete():
                return self._finish_clip()
            return None

    def _capture_frame_record(self) -> FrameRecord:
        raw = np.asarray(self._camera.read())
        return FrameRecord(raw=raw, display=self._prepare_display(raw))

    def _prepare_display(self, frame: np.ndarray) -> np.ndarray:
        import cv2

        source = np.asarray(frame)
        config = self._app_config.recording_manager.display
        contrast = config.contrast
        if contrast == 1.0 and not config.tone_enabled:
            return source.copy()

        brightness = config.tone_brightness if config.tone_enabled else 0.0
        return cv2.addWeighted(source, contrast, source, 0.0, brightness)

    def _post_roll_complete(self) -> bool:
        if self._post_roll_started_at is None:
            return False
        if len(self.post_buffer) == 0:
            return False

        wall_elapsed = time.monotonic() - self._post_roll_started_at
        return wall_elapsed >= self._app_config.recording_manager.post_roll_seconds

    def _finish_clip(self) -> ClipResult:
        encoding_fps = clip_encoding_fps(
            self.pre_buffer.capture_span(),
            self.post_buffer.capture_span(),
        )
        package = ClipPackage.build(
            self.pre_buffer.display_frames(),
            self.post_buffer.display_frames(),
            triggered_at=self._triggered_at,
            event_index=self._event_index,
        )
        result = self._recorder.write_clip(package, fps=encoding_fps)
        self.pre_buffer.clear()
        self.post_buffer.clear()
        self._clip_active = False
        self._post_roll_started_at = None
        self._triggered_at = None
        return result
