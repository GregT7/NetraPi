"""
TP-26: Stubbed event gate — all stop-sign types + ``record_safe_events`` (integration).

Injects ``DrivingEvent`` values via a stub ``evaluate`` (real EventManager not
required). Confirms unsafe types always write an MP4; ``COMPLETE_STOP`` only when
``record_safe_events`` is true. Clip write path matches TP-23 (pre-roll fill →
post-roll → ffmpeg H.264).

Usage (from repo root, Pi edge venv with camera + ffmpeg + optional Coral):

    python src/tests/integration/tp_26/tp_26_stubbed_event_gate_clips_integration.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

PRE_ROLL_SECONDS = 2.0
POST_ROLL_SECONDS = 2.0
PRE_FILL_LAP_BUDGET = 150
VERIFY_TPU = True
PREVIEW_ENABLED = False
FULL_RECORD = False


@dataclass(frozen=True)
class Scenario:
    label: str
    record_safe_events: bool
    event_type_name: str
    expect_clip: bool


# Covers all three StopSignEnum types + safe-gate matrix from TP-26 / AT-2.2.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        label="ROLLING_STOP + record_safe_events=false",
        record_safe_events=False,
        event_type_name="ROLLING_STOP",
        expect_clip=True,
    ),
    Scenario(
        label="RUN_THROUGH + record_safe_events=false",
        record_safe_events=False,
        event_type_name="RUN_THROUGH",
        expect_clip=True,
    ),
    Scenario(
        label="COMPLETE_STOP + record_safe_events=false",
        record_safe_events=False,
        event_type_name="COMPLETE_STOP",
        expect_clip=False,
    ),
    Scenario(
        label="COMPLETE_STOP + record_safe_events=true",
        record_safe_events=True,
        event_type_name="COMPLETE_STOP",
        expect_clip=True,
    ),
)


class _DeferredEventStub:
    """Armed stub: ready_to_evaluate when set; evaluate returns the fixed event."""

    def __init__(self) -> None:
        self._event = None

    @property
    def needs_detection(self) -> bool:
        return True

    @property
    def ready_to_evaluate(self) -> bool:
        return self._event is not None

    def arm(self, event) -> None:
        self._event = event

    def clear(self) -> None:
        self._event = None

    def observe(self, pre_buffer, *, now=None) -> None:
        return None

    def evaluate(self):
        event = self._event
        self._event = None
        return event


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _clip_files(clips_dir: Path) -> set[Path]:
    if not clips_dir.is_dir():
        return set()
    return {path.resolve() for path in clips_dir.rglob("*.mp4")}


def _pre_buffer_time_span(pre_buffer) -> float:
    records = pre_buffer._records
    if len(records) < 2:
        return 0.0
    return records[-1][0] - records[0][0]


def _pre_roll_window_full(pre_buffer) -> bool:
    if len(pre_buffer) == 0:
        return False
    config = pre_buffer._recording_manager_config
    if config is None:
        return False
    span_seconds = _pre_buffer_time_span(pre_buffer)
    return span_seconds >= config.pre_roll_seconds * config.coverage_tolerance


def _validate_pre_buffer(manager) -> None:
    pre_buffer = manager.pre_buffer
    if len(pre_buffer) == 0:
        raise RuntimeError("pre_buffer is empty; expected FrameRecord entries before clip")

    config = pre_buffer._recording_manager_config
    if config is None:
        raise RuntimeError("pre_buffer missing RecordingManagerConfig")

    pre_roll_seconds = config.pre_roll_seconds
    span_seconds = _pre_buffer_time_span(pre_buffer)
    min_span = pre_roll_seconds * config.coverage_tolerance
    if span_seconds < min_span:
        raise RuntimeError(
            f"pre_buffer window not full: oldest→newest span {span_seconds:.2f}s < "
            f"{min_span:.2f}s ({pre_roll_seconds:g}s pre_roll at "
            f"{config.coverage_tolerance:.0%} coverage tolerance)"
        )

    max_span = pre_roll_seconds * 1.05 + 0.75
    if span_seconds > max_span:
        raise RuntimeError(
            f"pre_buffer span {span_seconds:.2f}s exceeds configured window "
            f"({pre_roll_seconds:g}s pre_roll); eviction may be broken"
        )

    for index, display in enumerate(pre_buffer.display_frames()):
        if display.ndim != 3:
            raise RuntimeError(f"pre_buffer[{index}].display must be 3-D, got {display.shape}")
        if display.size == 0:
            raise RuntimeError(f"pre_buffer[{index}].display is empty")


def _post_roll_lap_budget(capture_fps: float) -> int:
    return max(1, math.ceil(POST_ROLL_SECONDS * capture_fps - 1e-9))


def _apply_test_config(
    app_config,
    *,
    repo_root: Path,
    resolve_runtime_paths: Callable,
    record_safe_events: bool,
):
    app_config = resolve_runtime_paths(app_config, repo_root)
    recording = app_config.recording_manager
    app_config = replace(
        app_config,
        recording_manager=replace(
            recording,
            pre_roll_seconds=PRE_ROLL_SECONDS,
            post_roll_seconds=POST_ROLL_SECONDS,
            record_safe_events=record_safe_events,
        ),
    )
    if not PREVIEW_ENABLED:
        app_config = replace(
            app_config,
            preview=replace(app_config.preview, enabled=False),
        )
    return app_config


def _verify_mp4_playable(path: Path) -> tuple[int, float]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open MP4 for playback: {path}")

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"unable to read first frame from {path}")
        if frame.ndim != 3 or frame.size == 0:
            raise RuntimeError(f"first frame from {path} is not a non-empty 3-D array")
        return frame_count, fps
    finally:
        capture.release()


def _validate_written_clip(
    manager,
    *,
    scenario: Scenario,
    new_clips: set[Path],
) -> Path:
    if manager.clip_active:
        raise RuntimeError(f"{scenario.label}: clip_active still true after write")
    if len(manager.post_buffer) != 0:
        raise RuntimeError(
            f"{scenario.label}: post_buffer should be empty after save, "
            f"got {len(manager.post_buffer)}"
        )
    if len(new_clips) != 1:
        names = ", ".join(path.name for path in sorted(new_clips))
        raise RuntimeError(
            f"{scenario.label}: expected exactly 1 new clip, got {len(new_clips)}: {names}"
        )

    clip_path = next(iter(new_clips))
    frame_count, _fps = _verify_mp4_playable(clip_path)
    if frame_count < 2:
        raise RuntimeError(
            f"{scenario.label}: clip {clip_path.name} has {frame_count} frames; "
            "expected at least 2 (pre + post)"
        )
    return clip_path


def _run_expect_no_clip(
    *,
    scenario: Scenario,
    base_config,
    repo_root: Path,
    resolve_runtime_paths,
    build_pipeline,
    DrivingEvent,
    StopSignEnum,
) -> None:
    app_config = _apply_test_config(
        base_config,
        repo_root=repo_root,
        resolve_runtime_paths=resolve_runtime_paths,
        record_safe_events=scenario.record_safe_events,
    )
    clips_dir = app_config.recording_manager.clips_dir
    clips_before = _clip_files(clips_dir)

    pipeline = build_pipeline(app_config)
    manager = pipeline.manager
    stub = _DeferredEventStub()
    event = DrivingEvent(type=getattr(StopSignEnum, scenario.event_type_name))
    stub.arm(event)
    manager._event_manager = stub

    print(f"\nScenario: {scenario.label} (expect no clip) ...")
    manager._camera.open()
    try:
        manager.run_one_lap(full_record=False)
    finally:
        manager._camera.close()
        manager.recorder.release()
        manager._trip_recorder.stop()

    if manager.clip_active:
        raise RuntimeError(
            f"{scenario.label}: expected clip_active=false, got true"
        )
    new_clips = _clip_files(clips_dir) - clips_before
    if new_clips:
        names = ", ".join(path.name for path in sorted(new_clips))
        raise RuntimeError(f"{scenario.label}: unexpected new clip(s): {names}")
    print(f"  clip_active={manager.clip_active}; no new MP4 (ok)")


def _run_expect_clip(
    *,
    scenario: Scenario,
    base_config,
    repo_root: Path,
    resolve_runtime_paths,
    build_pipeline,
    DrivingEvent,
    StopSignEnum,
) -> Path:
    app_config = _apply_test_config(
        base_config,
        repo_root=repo_root,
        resolve_runtime_paths=resolve_runtime_paths,
        record_safe_events=scenario.record_safe_events,
    )
    clips_dir = app_config.recording_manager.clips_dir
    clips_before = _clip_files(clips_dir)
    post_lap_budget = _post_roll_lap_budget(float(app_config.camera.recommended_fps))
    max_laps = PRE_FILL_LAP_BUDGET + post_lap_budget + 60

    pipeline = build_pipeline(app_config)
    manager = pipeline.manager
    stub = _DeferredEventStub()
    manager._event_manager = stub
    event = DrivingEvent(type=getattr(StopSignEnum, scenario.event_type_name))

    phase = "prefill"
    idle_laps = 0

    def should_stop() -> bool:
        nonlocal phase, idle_laps
        if _clip_files(clips_dir) - clips_before:
            return True
        if phase == "prefill":
            idle_laps += 1
            if idle_laps > PRE_FILL_LAP_BUDGET:
                return True
            if _pre_roll_window_full(manager.pre_buffer):
                _validate_pre_buffer(manager)
                span = _pre_buffer_time_span(manager.pre_buffer)
                print(
                    f"\n  Arming stub {scenario.event_type_name} after {idle_laps} "
                    f"idle lap(s) (pre_buffer={len(manager.pre_buffer)}, "
                    f"span={span:.2f}s) ..."
                )
                stub.arm(event)
                phase = "armed"
            return False
        if phase == "armed":
            if manager.clip_active:
                phase = "post"
            return False
        if phase == "post":
            if not manager.clip_active:
                return True
            return False
        return True

    print(f"\nScenario: {scenario.label} (expect MP4) ...")
    print(f"  max_laps={max_laps}")
    manager.run_loop(
        max_laps=max_laps,
        should_stop=should_stop,
        full_record=FULL_RECORD,
    )

    new_clips = _clip_files(clips_dir) - clips_before
    if phase == "prefill":
        span = _pre_buffer_time_span(manager.pre_buffer)
        raise RuntimeError(
            f"{scenario.label}: never armed stub "
            f"(idle_laps={idle_laps}, span={span:.2f}s, max_laps={max_laps})"
        )
    if phase == "armed" and not manager.clip_active and not new_clips:
        raise RuntimeError(
            f"{scenario.label}: stub armed but clip never started "
            f"(event={scenario.event_type_name}, "
            f"record_safe_events={scenario.record_safe_events})"
        )
    if not new_clips:
        raise RuntimeError(
            f"{scenario.label}: no new event clip "
            f"(phase={phase!r}, clip_active={manager.clip_active}, "
            f"idle_laps={idle_laps})"
        )

    clip_path = _validate_written_clip(manager, scenario=scenario, new_clips=new_clips)
    frame_count, clip_fps = _verify_mp4_playable(clip_path)
    print(f"  clip_path: {clip_path}")
    print(f"  clip_frame_count: {frame_count}")
    print(f"  clip_fps: {clip_fps:.2f}")
    return clip_path


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.events import DrivingEvent, StopSignEnum
    from netrapi.exceptions import NetraPiError

    config_dir = DEFAULT_CONFIG_DIR.resolve()

    try:
        base_config = AppConfig.load(config_dir)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    print("TP-26: Stubbed event gate — all stop-sign types + record_safe_events")
    print(f"  config_dir: {config_dir}")
    print(f"  pre_roll_seconds: {PRE_ROLL_SECONDS}")
    print(f"  post_roll_seconds: {POST_ROLL_SECONDS}")
    print(f"  preview: {'enabled' if PREVIEW_ENABLED else 'disabled'}")
    print(f"  verify_tpu: {VERIFY_TPU}")
    print(f"  scenarios: {len(SCENARIOS)}")

    written: list[tuple[str, Path]] = []

    try:
        for scenario in SCENARIOS:
            if scenario.expect_clip:
                clip_path = _run_expect_clip(
                    scenario=scenario,
                    base_config=base_config,
                    repo_root=REPO_ROOT,
                    resolve_runtime_paths=_resolve_runtime_paths,
                    build_pipeline=build_pipeline,
                    DrivingEvent=DrivingEvent,
                    StopSignEnum=StopSignEnum,
                )
                written.append((scenario.label, clip_path))
            else:
                _run_expect_no_clip(
                    scenario=scenario,
                    base_config=base_config,
                    repo_root=REPO_ROOT,
                    resolve_runtime_paths=_resolve_runtime_paths,
                    build_pipeline=build_pipeline,
                    DrivingEvent=DrivingEvent,
                    StopSignEnum=StopSignEnum,
                )
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).", file=sys.stderr)
        return 1

    print("\nResults:")
    for label, path in written:
        print(f"  [{label}] {path.name}")
    print(f"  no-clip scenarios: {sum(1 for s in SCENARIOS if not s.expect_clip)}")
    print("\nTP-26: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
