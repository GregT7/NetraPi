"""EventManager: Watching → CollectPostDrop FSM for stop-sign classification."""

from __future__ import annotations

import time
from collections import deque

from config.types import ApproachConfig, EventManagerConfig, MotionConfig
from netrapi.buffer import FrameBuffer
from netrapi.buffer.classification import Classification
from netrapi.events.approach import diagnose_approach_drop
from netrapi.events.approach.approach_drop_results import ApproachDropEvent
from netrapi.events.driving_event import ApproachSnapshot, DrivingEvent, PlaybackSeries
from netrapi.events.enums import EventPhase
from netrapi.events.classify import (
    LiveMotionTracker,
    StopClassifier,
    compute_approach_area_sum_pct,
    extract_stage1_features,
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
        self._area_stamp_snapshot: list[float] = []
        self._detect_frame: int = -1
        self._anchor_t: float | None = None
        self._motion_tracker = LiveMotionTracker(motion)
        self._latch_fps: float = fallback_fps
        self._ready_to_evaluate = False
        self._last_latched_approach: ApproachDropEvent | None = None

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

    @property
    def last_latched_approach(self) -> ApproachDropEvent | None:
        """ApproachDropEvent from the most recent Watching → CollectPostDrop latch."""
        return self._last_latched_approach

    def reset(self) -> None:
        self._phase = EventPhase.WATCHING
        self._area_history.clear()
        self._motion_history.clear()
        self._areas_snapshot = []
        self._area_stamp_snapshot = []
        self._detect_frame = -1
        self._anchor_t = None
        self._motion_tracker.reset()
        self._latch_fps = self._fallback_fps
        self._ready_to_evaluate = False
        self._last_latched_approach = None

    def observe(self, pre_buffer: FrameBuffer, *, now: float | None = None) -> bool:
        """Per-lap collection and FSM. Never classifies.

        Returns True when an approach is latched this call (Watching → CollectPostDrop).
        """
        if self._phase not in (EventPhase.WATCHING, EventPhase.COLLECT_POST_DROP):
            raise EventError(f"unrecognized event phase: {self._phase!r}")

        clock = time.monotonic() if now is None else now
        try:
            record = pre_buffer.latest()
        except BufferError:
            return False

        frame_bgr = record.display if record.display is not None else record.raw

        if self._phase is EventPhase.WATCHING:
            self._observe_watching(area=max_stop_sign_area(record.classifications), frame_bgr=frame_bgr, clock=clock)
            return self._phase is EventPhase.COLLECT_POST_DROP

        self._observe_collect(frame_bgr=frame_bgr, clock=clock)
        return False

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

        prefix = self._areas_snapshot[: self._detect_frame + 1]
        diagnosis = diagnose_approach_drop(
            prefix, self._latch_fps, config=self._approach
        )
        if diagnosis is None or diagnosis.event is None:
            self.reset()
            raise EventError("stage-2 feature extraction failed")
        area_sum = compute_approach_area_sum_pct(
            self._areas_snapshot, diagnosis.event
        )
        if area_sum is None:
            self.reset()
            raise EventError("stage-2 feature extraction failed")
        stage2 = [stage1[1], area_sum]

        try:
            stop_type = self._classifier.classify(stage1, stage2)
        except Exception:
            self.reset()
            raise

        winner = next(
            (
                candidate
                for candidate in diagnosis.peak_candidates
                if candidate.passed
                and candidate.peak_index == diagnosis.event.peak_index
            ),
            None,
        )
        approach = None
        if winner is not None and winner.drop_duration_s is not None:
            approach = ApproachSnapshot(
                peak_area_pct=winner.peak_area_pct,
                approach_duration_s=winner.approach_duration_s or 0.0,
                increasing_fraction=winner.increasing_fraction or 0.0,
                log_linear_r2=winner.log_linear_r2 or 0.0,
                drop_duration_s=winner.drop_duration_s,
                post_drop_holds=bool(winner.post_drop_holds),
                fail_reasons=winner.fail_reasons,
            )

        playback = PlaybackSeries(
            area_points=self._playback_area_points(),
            motion_points=tuple(self._motion_history),
            anchor_t=self._anchor_t,
            evaluate_t=time.monotonic(),
        )
        self.reset()
        return DrivingEvent(
            type=stop_type,
            knn_stage1=tuple(stage1),
            knn_stage2=tuple(stage2),
            approach=approach,
            playback_series=playback,
        )

    def _playback_area_points(self) -> tuple[tuple[float, float], ...]:
        if (
            self._area_stamp_snapshot
            and len(self._area_stamp_snapshot) == len(self._areas_snapshot)
        ):
            return tuple(zip(self._area_stamp_snapshot, self._areas_snapshot))
        if not self._areas_snapshot or self._anchor_t is None:
            return ()
        fps = self._latch_fps if self._latch_fps > 0 else self._fallback_fps
        dt = 1.0 / fps
        last = self._anchor_t
        n = len(self._areas_snapshot)
        return tuple(
            (last - (n - 1 - index) * dt, value)
            for index, value in enumerate(self._areas_snapshot)
        )

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

        self._area_stamp_snapshot = [stamp for stamp, _ in self._area_history]
        self._areas_snapshot = list(areas)
        self._detect_frame = len(self._areas_snapshot) - 1
        self._anchor_t = clock
        self._latch_fps = fps
        self._last_latched_approach = diagnosis.event
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
