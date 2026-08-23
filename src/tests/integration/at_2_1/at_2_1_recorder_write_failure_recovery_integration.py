"""
AT-2.1: Recorder write failure and recovery (integration).

Injects a failure on the first ``Recorder.write_clip`` call, verifies the run
ends cleanly (recorder released, camera closed), then runs a second session where
clip write succeeds.

Usage (from repo root, Pi edge venv with camera, display for preview, optional Coral):

    python src/tests/integration/at_2_1/at_2_1_recorder_write_failure_recovery_integration.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

PRE_ROLL_SECONDS = 2.0
POST_ROLL_SECONDS = 2.0
PRE_FILL_LAP_BUDGET = 150
VERIFY_TPU = True


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _clip_files(clips_dir: Path) -> set[Path]:
    if not clips_dir.is_dir():
        return set()
    return {path.resolve() for path in clips_dir.glob("clip_*.mp4")}


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
    return _pre_buffer_time_span(pre_buffer) >= config.pre_roll_seconds * config.coverage_tolerance


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths):
    """Preview and trip recording are always on for AT-2.1."""
    app_config = resolve_runtime_paths(app_config, repo_root)
    recording = app_config.recording_manager
    return replace(
        app_config,
        preview=replace(app_config.preview, enabled=True),
        trip_recorder=replace(app_config.trip_recorder, enabled=True),
        recording_manager=replace(
            recording,
            pre_roll_seconds=PRE_ROLL_SECONDS,
            post_roll_seconds=POST_ROLL_SECONDS,
        ),
    )


def _post_roll_lap_budget(capture_fps: float) -> int:
    return max(1, math.ceil(POST_ROLL_SECONDS * capture_fps - 1e-9))


def _assert_recorder_released(manager, *, context: str) -> None:
    if manager.recorder._out_path is not None:
        raise RuntimeError(f"{context}: Recorder still has an active output path")


def _assert_camera_closed(camera) -> None:
    from netrapi.exceptions import CameraError

    try:
        camera.read()
    except CameraError as exc:
        if "not open" in str(exc).lower():
            return
        raise
    raise RuntimeError("camera.read() succeeded; device was not released")


def _run_clip_cycle(manager, *, clips_dir: Path, clips_before: set[Path], label: str) -> Path:
    phase = "prefill"
    idle_laps = 0
    post_lap_budget = _post_roll_lap_budget(float(manager.camera.capture_fps))
    max_laps = PRE_FILL_LAP_BUDGET + post_lap_budget + 60

    def should_stop() -> bool:
        nonlocal phase, idle_laps
        if _clip_files(clips_dir) - clips_before:
            return True
        if phase == "prefill":
            idle_laps += 1
            if idle_laps > PRE_FILL_LAP_BUDGET:
                return True
            if _pre_roll_window_full(manager.pre_buffer):
                print(f"  {label}: begin_clip() after {idle_laps} idle lap(s) ...")
                manager.begin_clip()
                phase = "post"
            return False
        if phase == "post" and not manager.clip_active:
            return True
        return False

    manager.run_loop(max_laps=max_laps, should_stop=should_stop, full_record=True)
    new_clips = _clip_files(clips_dir) - clips_before
    if len(new_clips) != 1:
        names = ", ".join(path.name for path in sorted(new_clips))
        raise RuntimeError(f"{label}: expected 1 new clip, got {len(new_clips)}: {names}")
    return next(iter(new_clips))


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.exceptions import NetraPiError, RecordingError

    config_dir = DEFAULT_CONFIG_DIR.resolve()

    try:
        app_config = AppConfig.load(config_dir)
        app_config = _apply_test_config(
            app_config,
            repo_root=REPO_ROOT,
            resolve_runtime_paths=_resolve_runtime_paths,
        )
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    clips_dir = app_config.recording_manager.clips_dir
    trips_dir = app_config.trip_recorder.segments_dir

    print("AT-2.1: Recorder write failure and recovery")
    print(f"  config_dir: {config_dir}")
    print(f"  clips_dir: {clips_dir}")
    print(f"  trips_dir: {trips_dir}")
    print(f"  preview enabled: {app_config.preview.enabled} (forced on)")
    print(f"  trip_recorder enabled: {app_config.trip_recorder.enabled} (forced on)")
    print(f"  pre_roll_seconds: {PRE_ROLL_SECONDS}")
    print(f"  post_roll_seconds: {POST_ROLL_SECONDS}")

    try:
        pipeline = build_pipeline(app_config)
        manager = pipeline.manager
        original_write = manager.recorder.write_clip
        injected = {"count": 0}

        def _write_clip_with_first_failure(package, *, fps: float):
            injected["count"] += 1
            if injected["count"] == 1:
                raise RecordingError("AT-2.1 injected write_clip failure")
            return original_write(package, fps=fps)

        manager.recorder.write_clip = _write_clip_with_first_failure  # type: ignore[method-assign]

        clips_before_fail = _clip_files(clips_dir)
        print("\nPhase 1: trigger clip with injected write failure ...")
        try:
            _run_clip_cycle(
                manager,
                clips_dir=clips_dir,
                clips_before=clips_before_fail,
                label="failure run",
            )
        except RecordingError as exc:
            print(f"  write failure surfaced: {exc}")
        else:
            raise RuntimeError("Phase 1: expected RecordingError from injected write_clip failure")

        _assert_recorder_released(manager, context="after failure")
        _assert_camera_closed(manager.camera)
        if _clip_files(clips_dir) - clips_before_fail:
            raise RuntimeError("Phase 1: clip file written despite injected failure")

        print("\nPhase 2: trigger clip with normal writer path ...")
        clips_before_ok = _clip_files(clips_dir)
        clip_path = _run_clip_cycle(
            manager,
            clips_dir=clips_dir,
            clips_before=clips_before_ok,
            label="recovery run",
        )
        _assert_recorder_released(manager, context="after recovery clip")
        print(f"  recovery clip: {clip_path.name}")
        print(f"  injected write_clip calls: {injected['count']}")
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    print("\nAT-2.1: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
