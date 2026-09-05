from __future__ import annotations

import signal
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import numpy as np

from config.loader import AppConfig

from netrapi.buffer import FrameBuffer, FrameRecord
from netrapi.buzzer import Buzzer
from netrapi.capture import Camera, PreviewUI
from netrapi.detection import Detector
from netrapi.events import EventManager
from netrapi.events.driving_event import DrivingEvent, PlaybackSeries
from netrapi.recording.clip_package import ClipPackage
from netrapi.recording.clip_result import ClipResult
from netrapi.recording.playback_json import write_playback_sidecars
from netrapi.recording.util.encoding_fps import clip_encoding_fps
from netrapi.recording.recorder import Recorder
from netrapi.recording.trip_recorder import TripRecorder
from netrapi.trip_log import TripSessionLog


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
        local_store=None,
        cloud_ingest=None,
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
        self._local_store = local_store
        self._cloud_ingest = cloud_ingest
        self._boot_issues: list[str] = []
        self._trip_log: TripSessionLog | None = None

        self._clip_active = False
        self._running = False
        self._post_roll_started_at: float | None = None
        self._triggered_at: datetime | None = None
        self._event_index = 0
        self._driving_session_id: int | None = None
        self._pending_event_id: int | None = None
        self._pending_playback: PlaybackSeries | None = None
        self._pending_classification: str | None = None
        self._open_trip_segment_id: int | None = None
        self._open_trip_segment_start: datetime | None = None
        if local_store is not None and hasattr(trip_recorder, "set_on_segment_saved"):
            trip_recorder.set_on_segment_saved(self._persist_saved_segment)
        if local_store is not None and hasattr(trip_recorder, "set_on_segment_opened"):
            trip_recorder.set_on_segment_opened(self._prime_open_segment)

    def _emit(self, message: str) -> None:
        if self._trip_log is not None:
            self._trip_log.write(message)
        else:
            print(message, flush=True)

    def _open_trip_log(self, session_id: int | None) -> None:
        self._close_trip_log()
        trip_cfg = self._app_config.trip_recorder
        self._trip_log = TripSessionLog.open(
            trip_cfg.logs_dir,
            session_id=session_id,
            stats_interval_s=trip_cfg.stats_interval_s,
        )
        self._trip_recorder.set_log(self._trip_log.write)
        if self._cloud_ingest is not None and hasattr(self._cloud_ingest, "set_log"):
            self._cloud_ingest.set_log(self._trip_log.write)

    def _close_trip_log(self) -> None:
        if self._trip_log is None:
            return
        log = self._trip_log
        self._trip_log = None
        self._trip_recorder.set_log(None)
        if self._cloud_ingest is not None and hasattr(self._cloud_ingest, "set_log"):
            self._cloud_ingest.set_log(None)
        log.close()

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

    def set_boot_issues(self, messages: list[str]) -> None:
        self._boot_issues = list(messages)

    def disable_cloud(self, reason: str) -> None:
        if self._cloud_ingest is None:
            return
        self._emit(f"[health] disabling cloud ingest: {reason}")
        self._cloud_ingest = None
        self._record_exception(reason, is_fatal=False)

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
            if self._local_store is not None:
                master_config_id = self._local_store.ensure_config_snapshot(
                    self._app_config.config_dir
                )
                self._try_ingest("sync_master_config", master_config_id)
                self._driving_session_id = self._local_store.start_session(
                    start_time=datetime.now(),
                    master_config_id=master_config_id,
                )
                self._open_trip_log(self._driving_session_id)
                self._emit(f"[session] driving_session {self._driving_session_id} started")
                self._try_ingest("sync_session", self._driving_session_id)
                for message in self._boot_issues:
                    self._record_exception(message, is_fatal=False)
                self._boot_issues.clear()
            else:
                self._open_trip_log(None)
                self._emit("[session] started (no local store)")
            laps = 0
            while self._running:
                if should_stop and should_stop():
                    break
                if max_laps is not None and laps >= max_laps:
                    break
                self.run_one_lap(full_record=trip_enabled)
                laps += 1
        except Exception as exc:
            self._record_exception(str(exc), is_fatal=True)
            raise
        finally:
            signal.signal(signal.SIGINT, previous_handler)
            self._buzzer.close()
            self._camera.close()
            self._recorder.release()
            self._trip_recorder.stop()
            if self._local_store is not None and self._driving_session_id is not None:
                self._local_store.end_session(
                    self._driving_session_id, end_time=datetime.now()
                )
                self._try_ingest("sync_session", self._driving_session_id)
                self._emit(f"[session] driving_session {self._driving_session_id} ended")
            self._close_trip_log()

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
            if self._event_manager.observe(self.pre_buffer):
                latched = self._event_manager.last_latched_approach
                if latched is not None:
                    self._emit(
                        f"[approach] detected peak={latched.peak_area_pct:.2f}% "
                        f"approach={latched.approach_duration_s:.2f}s "
                        f"drop={latched.drop_duration_s:.2f}s "
                        f"score={latched.score:.3f}"
                    )
                else:
                    self._emit("[approach] detected")
            if self._event_manager.ready_to_evaluate:
                event = self._event_manager.evaluate()
                self._buzzer.beep(event)
                self._emit(
                    f"[event] {event.type.model_label} "
                    f"unsafe={event.is_unsafe}"
                )
                self._commit_evaluated_event(event)
                if (
                    event.is_unsafe
                    or self._app_config.recording_manager.record_safe_events
                ):
                    self.begin_clip()
                else:
                    # Metadata already synced; no clip will call attach.
                    self._pending_event_id = None
                    self._pending_playback = None
                    self._pending_classification = None
            return None
        else:
            self.post_buffer.append(record)
            if self._post_roll_complete():
                return self._finish_clip()
            return None

    def _commit_evaluated_event(self, event: DrivingEvent) -> None:
        """Persist event metadata (and sync) immediately; clip attach is separate."""
        if self._local_store is None or self._driving_session_id is None:
            return
        event_time = datetime.now()
        trip_segment_id, trip_offset = self._event_trip_location(event_time)
        approach = None
        if event.approach is not None:
            approach = {
                "peak_area_pct": event.approach.peak_area_pct,
                "approach_duration_s": event.approach.approach_duration_s,
                "increasing_fraction": event.approach.increasing_fraction,
                "log_linear_r2": event.approach.log_linear_r2,
                "drop_duration_s": event.approach.drop_duration_s,
                "post_drop_holds": event.approach.post_drop_holds,
                "fail_reasons": list(event.approach.fail_reasons),
            }
        event_id = self._local_store.persist_event(
            driving_session_id=self._driving_session_id,
            time=event_time,
            type_value=event.type.model_label,
            knn_stage1=event.knn_stage1,
            knn_stage2=event.knn_stage2,
            approach=approach,
            trip_segment_id=trip_segment_id,
            trip_offset_seconds=trip_offset,
        )
        self._pending_event_id = event_id
        self._pending_playback = event.playback_series
        self._pending_classification = event.type.model_label
        self._try_ingest("sync_event", event_id)

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
        write_playback_sidecars(
            result.clip_path,
            self._pending_playback,
            pre_roll_seconds=self._app_config.recording_manager.pre_roll_seconds,
            classification=self._pending_classification or "",
        )
        event_id = self._pending_event_id
        self._pending_event_id = None
        self._pending_playback = None
        self._pending_classification = None
        if (
            self._local_store is not None
            and event_id is not None
            and self._triggered_at is not None
        ):
            config = self._app_config.recording_manager
            fps = max(1, int(round(encoding_fps)))
            self._local_store.attach_clip(
                event_id,
                clip_path=result.clip_path,
                fps=fps,
                order_number=package.event_index,
                num_frames=result.pre_frame_count + result.post_frame_count,
                clip_start=self._triggered_at
                - timedelta(seconds=config.pre_roll_seconds),
                clip_end=self._triggered_at
                + timedelta(seconds=config.post_roll_seconds),
            )
            self._try_ingest("sync_event", event_id)
        self.pre_buffer.clear()
        self.post_buffer.clear()
        self._clip_active = False
        self._post_roll_started_at = None
        self._triggered_at = None
        return result

    def _prime_open_segment(
        self,
        *,
        local_path: Path,
        order_number: int,
        start_time: datetime,
    ) -> None:
        if self._local_store is None or self._driving_session_id is None:
            return
        self._open_trip_segment_id = self._local_store.persist_trip_segment(
            driving_session_id=self._driving_session_id,
            local_path=local_path,
            start_time=start_time,
            end_time=start_time,
            order_number=order_number,
            init_local_stored=None,
        )
        self._open_trip_segment_start = start_time
        self._try_ingest("sync_trip_segment", self._open_trip_segment_id)

    def _persist_saved_segment(
        self,
        *,
        local_path: Path,
        order_number: int,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        if self._local_store is None or self._driving_session_id is None:
            return
        if self._open_trip_segment_id is not None:
            self._local_store.update_trip_segment(
                self._open_trip_segment_id,
                local_path=local_path,
                end_time=end_time,
                init_local_stored=True,
            )
            self._try_ingest("sync_trip_segment", self._open_trip_segment_id)
            return
        segment_id = self._local_store.persist_trip_segment(
            driving_session_id=self._driving_session_id,
            local_path=local_path,
            start_time=start_time,
            end_time=end_time,
            order_number=order_number,
        )
        self._try_ingest("sync_trip_segment", segment_id)

    def _event_trip_location(
        self, event_time: datetime
    ) -> tuple[int | None, float | None]:
        if self._open_trip_segment_id is None or self._open_trip_segment_start is None:
            return None, None
        offset = (event_time - self._open_trip_segment_start).total_seconds()
        return self._open_trip_segment_id, max(0.0, offset)

    def _record_exception(self, message: str, *, is_fatal: bool) -> None:
        self._emit(f"[exception] {'fatal' if is_fatal else 'warn'}: {message}")
        if self._local_store is None or self._driving_session_id is None:
            return
        try:
            exception_id = self._local_store.persist_exception(
                driving_session_id=self._driving_session_id,
                message=message,
                time=datetime.now(),
                is_fatal=is_fatal,
            )
        except Exception as exc:
            self._emit(f"[exception] persist failed: {exc}")
            return
        self._try_ingest("sync_operational_exception", exception_id)

    def _try_ingest(self, method_name: str, *args) -> None:
        if self._cloud_ingest is None:
            return
        try:
            getattr(self._cloud_ingest, method_name)(*args)
        except Exception as exc:
            self._emit(f"[ingest] {method_name} failed: {exc}")
            if method_name != "sync_operational_exception":
                self._record_exception(
                    f"ingest {method_name} failed: {exc}", is_fatal=False
                )
