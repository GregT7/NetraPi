"""
TP-23: RecordingManager clip-active path and MP4 output (integration).

Runs ``RecordingManager.run_loop()`` on the Pi, fills the time-windowed ``pre_buffer``,
calls ``begin_clip()`` as a test hook, then continues until wall-clock post-roll completes
and ``Recorder.write_clip`` saves an H.264 event MP4 via ffmpeg.

Usage (from repo root, Pi edge venv with camera + optional Coral):

    python src/tests/integration/tp_23/tp_23_clip_active_mp4_integration.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

# Shorter rolls than production config so the test finishes in ~seconds on-device.
PRE_ROLL_SECONDS = 2.0
POST_ROLL_SECONDS = 2.0
# Lap budget to fill pre_roll window before triggering begin_clip().
PRE_FILL_LAP_BUDGET = 150
VERIFY_TPU = True
PREVIEW_ENABLED = False
FULL_RECORD = False


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _clip_files(clips_dir: Path) -> set[Path]:
    if not clips_dir.is_dir():
        return set()
    return {path.resolve() for path in clips_dir.glob("*.mp4")}


def _trip_files(trips_dir: Path) -> set[Path]:
    if not trips_dir.is_dir():
        return set()
    return {path.resolve() for path in trips_dir.glob("*.mp4")}


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


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths):
    app_config = resolve_runtime_paths(app_config, repo_root)
    recording = app_config.recording_manager
    app_config = replace(
        app_config,
        recording_manager=replace(
            recording,
            pre_roll_seconds=PRE_ROLL_SECONDS,
            post_roll_seconds=POST_ROLL_SECONDS,
        ),
    )
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


def _post_roll_lap_budget(capture_fps: float) -> int:
    """Heuristic lap headroom so wall-clock post_roll_seconds can elapse."""
    return max(1, math.ceil(POST_ROLL_SECONDS * capture_fps - 1e-9))


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


def _validate_clip_result(
    manager,
    *,
    new_clips: set[Path],
    expected_min_frames: int,
) -> Path:
    if manager.clip_active:
        raise RuntimeError("clip_active is still true after run_loop finished")

    if len(manager.post_buffer) != 0:
        raise RuntimeError(
            f"post_buffer should be empty after clip save, got {len(manager.post_buffer)} entries"
        )
    if len(new_clips) != 1:
        names = ", ".join(path.name for path in sorted(new_clips))
        raise RuntimeError(f"expected exactly 1 new clip file, got {len(new_clips)}: {names}")

    clip_path = next(iter(new_clips))
    if not clip_path.is_file():
        raise RuntimeError(f"clip file missing: {clip_path}")

    frame_count, _fps = _verify_mp4_playable(clip_path)
    if frame_count < expected_min_frames:
        raise RuntimeError(
            f"clip {clip_path.name} has {frame_count} frames; "
            f"expected at least {expected_min_frames}"
        )
    return clip_path


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
    post_lap_budget = _post_roll_lap_budget(float(app_config.camera.recommended_fps))
    max_laps = PRE_FILL_LAP_BUDGET + post_lap_budget + 60

    print("TP-23: RecordingManager clip-active path and MP4 output")
    print(f"  config_dir: {config_dir}")
    print(f"  clips_dir: {clips_dir}")
    print(f"  trips_dir: {trips_dir}")
    print(f"  pre_roll_seconds: {PRE_ROLL_SECONDS}")
    print(f"  post_roll_seconds: {POST_ROLL_SECONDS}")
    print(f"  pre_fill_lap_budget: {PRE_FILL_LAP_BUDGET}")
    print(f"  post_roll_lap_budget (initial): {post_lap_budget}")
    print(f"  max_laps: {max_laps}")
    print(f"  preview: {'enabled' if PREVIEW_ENABLED else 'disabled'}")
    print(f"  verify_tpu: {VERIFY_TPU}")
    print(f"  full_record: {FULL_RECORD}")

    try:
        pipeline = build_pipeline(app_config, verify_tpu=VERIFY_TPU)
        manager = pipeline.manager

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
                        f"\nTriggering begin_clip() after {idle_laps} idle lap(s) "
                        f"(pre_buffer={len(manager.pre_buffer)} frame(s), "
                        f"span={span:.2f}s) ..."
                    )
                    manager.begin_clip()
                    phase = "post"
                return False
            if phase == "post":
                if not manager.clip_active:
                    return True
                return False
            return True

        print(
            f"\nFill pre_buffer, trigger clip, post-roll (max_laps={max_laps}) ..."
        )
        manager.run_loop(
            max_laps=max_laps,
            should_stop=should_stop,
            full_record=FULL_RECORD,
        )

        clips_after = _clip_files(clips_dir)
        trips_after = _trip_files(trips_dir)
        new_clips = clips_after - clips_before
        new_trips = trips_after - trips_before
        if phase == "prefill":
            span = _pre_buffer_time_span(manager.pre_buffer)
            reason = (
                f"exceeded pre_fill_lap_budget={PRE_FILL_LAP_BUDGET}"
                if idle_laps > PRE_FILL_LAP_BUDGET
                else "pre_buffer never reached full pre_roll window"
            )
            raise RuntimeError(
                f"run_loop finished without triggering begin_clip: {reason} "
                f"(idle_laps={idle_laps}, span={span:.2f}s, "
                f"pre_roll={PRE_ROLL_SECONDS:g}s, max_laps={max_laps})"
            )
        if not new_clips:
            raise RuntimeError(
                "run_loop finished without writing a new event clip "
                f"(phase={phase!r}, clip_active={manager.clip_active}, "
                f"idle_laps={idle_laps}, pre_buffer={len(manager.pre_buffer)}, "
                f"post_buffer={len(manager.post_buffer)}, max_laps={max_laps})"
            )
        clip_path = _validate_clip_result(
            manager,
            new_clips=new_clips,
            expected_min_frames=2,
        )
        frame_count, clip_fps = _verify_mp4_playable(clip_path)

        print("\nResults:")
        print(f"  camera recommended_fps: {app_config.camera.recommended_fps:.2f}")
        print(f"  capture_fps in use: {manager.camera.capture_fps:.2f}")
        print(f"  clip_active: {manager.clip_active}")
        print(f"  pre_buffer entries: {len(manager.pre_buffer)}")
        print(f"  post_buffer entries: {len(manager.post_buffer)}")
        print(f"  event clip files before: {len(clips_before)}")
        print(f"  event clip files after: {len(clips_after)}")
        print(f"  new event clip files: {len(new_clips)}")
        print(f"  clip_path: {clip_path}")
        print(f"  clip_frame_count: {frame_count}")
        print(f"  clip_fps: {clip_fps:.2f}")
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

    print("\nTP-23: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

