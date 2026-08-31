"""
TP-22: RecordingManager idle run loop integration.

Runs ``RecordingManager.run_loop()`` for a bounded number of laps on the Pi with
a USB camera and Coral detector. Verifies the idle path (camera → ``FrameRecord``
→ ``pre_buffer.push``) without writing event clips.

Before the main loop, ``run_loop`` opens the camera and runs capture → ``FrameRecord`` → ``pre_buffer.push`` without writing event clips.

Clip and trip MP4 output uses ffmpeg H.264. Clip FPS is derived from buffer capture timestamps at write time; trip segments buffer frames in RAM and encode once per segment with ``frame_count / wall_elapsed``.

When ``FULL_RECORD`` is True, trip segments are written under ``src/main/data/trips/``
(``trip_recorder.json`` → ``segments_dir``).

Usage (from repo root, Pi edge venv):

    python src/tests/integration/tp_22/tp_22_idle_run_loop_integration.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

MAX_LAPS = 300
VERIFY_TPU = True
FULL_RECORD = True
PREVIEW_ENABLED = True


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)

def _clip_files(clips_dir: Path) -> set[Path]:
    if not clips_dir.is_dir():
        return set()
    return {path.resolve() for path in clips_dir.rglob("*.mp4")}

def _trip_files(trips_dir: Path) -> set[Path]:
    if not trips_dir.is_dir():
        return set()
    return {path.resolve() for path in trips_dir.glob("*.mp4")}

def _pre_buffer_time_span(pre_buffer) -> float:
    records = pre_buffer._records
    if len(records) < 2:
        return 0.0
    return records[-1][0] - records[0][0]


def _validate_pre_buffer(manager) -> None:
    pre_buffer = manager.pre_buffer
    if len(pre_buffer) == 0:
        raise RuntimeError("pre_buffer is empty after run_loop; expected FrameRecord entries")

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


def _validate_idle_state(
    manager,
    clips_before: set[Path],
    clips_after: set[Path],
    *,
    full_record: bool,
    trips_before: set[Path],
    trips_after: set[Path],
) -> None:
    if manager.clip_active:
        raise RuntimeError("clip_active is true after idle-only run")

    new_clips = clips_after - clips_before
    if new_clips:
        names = ", ".join(path.name for path in sorted(new_clips))
        raise RuntimeError(f"unexpected event clip file(s) written during idle run: {names}")

    if full_record and not (trips_after - trips_before):
        raise RuntimeError("full_record enabled but no trip segment was written to trips_dir")


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths):
    app_config = resolve_runtime_paths(app_config, repo_root)
    if not PREVIEW_ENABLED:
        app_config = replace(
            app_config,
            preview=replace(app_config.preview, enabled=False),
        )
    if FULL_RECORD:
        app_config = replace(
            app_config,
            trip_recorder=replace(app_config.trip_recorder, enabled=True),
        )
    return app_config


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.exceptions import NetraPiError

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
    clips_before = _clip_files(clips_dir)
    trips_before = _trip_files(trips_dir)

    print("TP-22: RecordingManager idle run loop integration")
    print(f"  config_dir: {config_dir}")
    print(f"  max_laps: {MAX_LAPS}")
    print(f"  preview: {'enabled' if PREVIEW_ENABLED else 'disabled'}")
    print(f"  verify_tpu: {VERIFY_TPU}")
    print(f"  full_record: {FULL_RECORD}")
    print(f"  clips_dir: {clips_dir}")
    print(f"  trips_dir: {trips_dir}")
    print(f"  record_safe_events: {app_config.recording_manager.record_safe_events}")

    try:
        pipeline = build_pipeline(app_config)
        manager = pipeline.manager

        print(f"\nIdle run (max_laps={MAX_LAPS}, full_record={FULL_RECORD}) ...")
        manager.run_loop(
            max_laps=MAX_LAPS,
            full_record=FULL_RECORD,
        )

        clips_after = _clip_files(clips_dir)
        trips_after = _trip_files(trips_dir)
        _validate_pre_buffer(manager)
        new_clips = clips_after - clips_before
        new_trips = trips_after - trips_before
        _validate_idle_state(
            manager,
            clips_before,
            clips_after,
            full_record=FULL_RECORD,
            trips_before=trips_before,
            trips_after=trips_after,
        )

        sample = manager.pre_buffer.latest()
        pre_span = _pre_buffer_time_span(manager.pre_buffer)
        print("\nResults:")
        print(f"  camera recommended_fps: {app_config.camera.recommended_fps:.2f}")
        print(f"  pre_buffer entries: {len(manager.pre_buffer)}")
        print(f"  pre_buffer time span: {pre_span:.2f}s")
        print(f"  clip_active: {manager.clip_active}")
        print(f"  latest raw shape: {tuple(sample.raw.shape)} dtype={sample.raw.dtype}")
        print(f"  latest display shape: {tuple(sample.display.shape)} dtype={sample.display.dtype}")
        print(f"  event clip files before: {len(clips_before)}")
        print(f"  event clip files after: {len(clips_after)}")
        print(f"  new event clip files: {len(new_clips)}")
        print(f"  trip segment files before: {len(trips_before)}")
        print(f"  trip segment files after: {len(trips_after)}")
        print(f"  new trip segment files: {len(new_trips)}")
        if new_trips:
            for path in sorted(new_trips):
                print(f"    {path.name}")
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).", file=sys.stderr)
        return 1

    print("\nTP-22: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
