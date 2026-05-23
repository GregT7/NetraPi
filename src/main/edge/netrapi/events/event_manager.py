"""EventManager: Watching → CollectPostDrop FSM for stop-sign classification."""

from __future__ import annotations

import time
from collections import deque

from config.types import ApproachConfig, EventManagerConfig, MotionConfig
from netrapi.buffer import FrameBuffer
from netrapi.buffer.classification import Classification
from netrapi.events.approach import diagnose_approach_drop
from netrapi.events.driving_event import DrivingEvent
from netrapi.events.enums import EventPhase
from netrapi.events.classify import (
    LiveMotionTracker,
    StopClassifier,
    extract_stage1_features,
    extract_stage2_features,
)
from netrapi.exceptions import BufferError, EventError

_STOP_SIGN_LABEL = "stop sign"


def max_stop_sign_area(classifications: list[Classification]) -> float:
    """Largest stop-sign box area (normalized width×height)."""
    best = 0.0
    for item in classifications:
        if item.label.strip().lower() != _STOP_SIGN_LABEL:
            continue
        ymin, xmin, ymax, xmax = item.box
        width = max(0.0, float(xmax) - float(xmin))
        height = max(0.0, float(ymax) - float(ymin))
        best = max(best, width * height)
    return best


class EventManager:
    def __init__(
        self,
        config: EventManagerConfig,
        *,
        approach: ApproachConfig,
        motion: MotionConfig,
        classifier: StopClassifier,
        fallback_fps: float,
    ) -> None:
        if fallback_fps <= 0:
            raise ValueError("fallback_fps must be greater than 0")
        self._config = config
        self._approach = approach
        self._motion = motion
        self._classifier = classifier
        self._fallback_fps = fallback_fps

        self._phase = EventPhase.WATCHING
        self._area_history: deque[tuple[float, float]] = deque()
        self._motion_history: list[tuple[float, float]] = []
        self._areas_snapshot: list[float] = []
        self._detect_frame: int = -1
        self._anchor_t: float | None = None
        self._motion_tracker = LiveMotionTracker(motion)
        self._latch_fps: float = fallback_fps
        self._ready_to_evaluate = False

    @property
    def config(self) -> EventManagerConfig:
        return self._config

    @property
    def phase_name(self) -> str:
        return self._phase.name

    @property
    def needs_detection(self) -> bool:
        """True while Watching — RecordingManager should run the detector this lap."""
        return self._phase is EventPhase.WATCHING

    @property
    def ready_to_evaluate(self) -> bool:
        """True after CollectPostDrop window completes — call evaluate() this lap."""
        return self._ready_to_evaluate

    def reset(self) -> None:
        self._phase = EventPhase.WATCHING
        self._area_history.clear()
        self._motion_history.clear()
        self._areas_snapshot = []
        self._detect_frame = -1
        self._anchor_t = None
        self._motion_tracker.reset()
        self._latch_fps = self._fallback_fps
        self._ready_to_evaluate = False

    def observe(self, pre_buffer: FrameBuffer, *, now: float | None = None) -> None:
        """Per-lap collection and FSM. Never classifies."""
        if self._phase not in (EventPhase.WATCHING, EventPhase.COLLECT_POST_DROP):
            raise EventError(f"unrecognized event phase: {self._phase!r}")

        clock = time.monotonic() if now is None else now
        try:
            record = pre_buffer.latest()
        except BufferError:
            return

        frame_bgr = record.display if record.display is not None else record.raw

        if self._phase is EventPhase.WATCHING:
            area = max_stop_sign_area(record.classifications)
            self._observe_watching(area=area, frame_bgr=frame_bgr, clock=clock)
            return

        self._observe_collect(frame_bgr=frame_bgr, clock=clock)

    def evaluate(self) -> DrivingEvent:
        """Classify from latched histories. Call only when ready_to_evaluate."""
        if not self._ready_to_evaluate:
            raise EventError("evaluate() called before ready_to_evaluate")
        if self._anchor_t is None:
            self.reset()
            raise EventError("evaluate() missing latch state")

        stage1 = extract_stage1_features(
            self._motion_history,
            anchor_s=self._anchor_t,
            window_s=self._motion.post_drop_window_s,
            stopped_threshold=self._motion.stopped_motion_threshold,
        )
        if stage1 is None:
            self.reset()
            raise EventError("stage-1 feature extraction failed")

        stage2 = extract_stage2_features(
            stage1_features=stage1,
            areas_snapshot=self._areas_snapshot,
            detect_frame=self._detect_frame,
            fps=self._latch_fps,
            approach_config=self._approach,
        )
        if stage2 is None:
            self.reset()
            raise EventError("stage-2 feature extraction failed")

        try:
            stop_type = self._classifier.classify(stage1, stage2)
        except Exception:
            self.reset()
            raise

        self.reset()
        return DrivingEvent(type=stop_type)

    def _estimate_fps(self) -> float:
        if len(self._area_history) < 2:
            return self._fallback_fps
        t0 = self._area_history[0][0]
        t1 = self._area_history[-1][0]
        span = t1 - t0
        if span <= 1e-6:
            return self._fallback_fps
        return (len(self._area_history) - 1) / span

    def _evict_area_history(self, clock: float) -> None:
        cutoff = clock - self._config.area_history_seconds
        while self._area_history and self._area_history[0][0] < cutoff:
            self._area_history.popleft()

    def _observe_watching(self, *, area: float, frame_bgr, clock: float) -> None:
        self._area_history.append((clock, area))
        self._evict_area_history(clock)

        areas = [value for _, value in self._area_history]
        fps = self._estimate_fps()
        diagnosis = diagnose_approach_drop(areas, fps, config=self._approach)
        if diagnosis is None or diagnosis.event is None:
            return

        self._areas_snapshot = list(areas)
        self._detect_frame = len(self._areas_snapshot) - 1
        self._anchor_t = clock
        self._latch_fps = fps
        self._area_history.clear()
        self._motion_history.clear()
        self._motion_tracker.prime(frame_bgr)
        self._phase = EventPhase.COLLECT_POST_DROP
        self._ready_to_evaluate = False

    def _observe_collect(self, *, frame_bgr, clock: float) -> None:
        assert self._anchor_t is not None
        score = self._motion_tracker.score(frame_bgr)
        self._motion_history.append((clock, score))

        if clock - self._anchor_t < self._motion.post_drop_window_s:
            self._ready_to_evaluate = False
            return

        self._ready_to_evaluate = True
