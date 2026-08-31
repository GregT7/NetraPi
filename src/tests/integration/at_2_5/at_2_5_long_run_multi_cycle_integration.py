"""
AT-2.5: Long-run multi-cycle stability and resource hygiene (integration soak).

Runs multiple ``idle -> clip_active -> idle`` cycles in one process via a single
``RecordingManager.run_loop()`` session. Each cycle uses ``begin_clip()`` as a
test hook (same as TP-23), then validates buffers, recorder release, and a new
event MP4 before starting the next cycle.

Usage (from repo root, Pi edge venv with camera + optional Coral):

    python src/tests/integration/at_2_5/at_2_5_long_run_multi_cycle_integration.py
"""

from __future__ import annotations

import math
import resource
import sys
from dataclasses import dataclass, replace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

NUM_CYCLES = 3
PRE_ROLL_SECONDS = 2.0
POST_ROLL_SECONDS = 2.0
# Per-cycle lap budget to fill pre_roll window before triggering begin_clip().
PRE_FILL_LAP_BUDGET = 150
# Upper-bound lap headroom for max_laps planning before measured FPS is known.
POST_ROLL_LAP_BUDGET_MAX = 90
GAP_LAPS = 10
VERIFY_TPU = True
PREVIEW_ENABLED = True
FULL_RECORD = True
MAX_RSS_GROWTH_MB = 80.0


@dataclass
class CycleResult:
    index: int
    clip_path: Path
    frame_count: int
    pre_buffer_after: int
    post_buffer_after: int
    peak_rss_mb: float


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


def _post_roll_lap_budget(capture_fps: float) -> int:
    """Lap headroom so wall-clock post_roll_seconds can elapse at the given FPS."""
    return max(1, math.ceil(POST_ROLL_SECONDS * capture_fps - 1e-9))


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


def _peak_rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss / 1024.0


def _verify_mp4_playable(path: Path) -> int:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open MP4 for playback: {path}")

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"unable to read first frame from {path}")
        if frame.ndim != 3 or frame.size == 0:
            raise RuntimeError(f"first frame from {path} is not a non-empty 3-D array")
        return frame_count
    finally:
        capture.release()


def _assert_idle_state(manager, *, context: str) -> None:
    if manager.clip_active:
        raise RuntimeError(f"{context}: clip_active is still true")
    if len(manager.post_buffer) != 0:
        raise RuntimeError(
            f"{context}: post_buffer not empty ({len(manager.post_buffer)} entries)"
        )


def _assert_recorder_released(manager, *, context: str) -> None:
    if manager.recorder._out_path is not None:
        raise RuntimeError(f"{context}: Recorder still has an active output path")


def _finish_cycle(
    manager,
    *,
    cycle_index: int,
    clips_before_cycle: set[Path],
    clips_dir: Path,
) -> CycleResult:
    _assert_idle_state(manager, context=f"cycle {cycle_index} after clip save")
    _assert_recorder_released(manager, context=f"cycle {cycle_index} after clip save")

    clips_now = _clip_files(clips_dir)
    new_clips = clips_now - clips_before_cycle
    if len(new_clips) != 1:
        names = ", ".join(path.name for path in sorted(new_clips))
        raise RuntimeError(
            f"cycle {cycle_index}: expected 1 new clip, got {len(new_clips)}: {names}"
        )

    clip_path = next(iter(new_clips))
    frame_count = _verify_mp4_playable(clip_path)
    if frame_count < 2:
        raise RuntimeError(
            f"cycle {cycle_index}: clip {clip_path.name} has only {frame_count} frame(s)"
        )

    return CycleResult(
        index=cycle_index,
        clip_path=clip_path,
        frame_count=frame_count,
        pre_buffer_after=len(manager.pre_buffer),
        post_buffer_after=len(manager.post_buffer),
        peak_rss_mb=_peak_rss_mb(),
    )


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
    clips_before_run = _clip_files(clips_dir)
    per_cycle_laps = PRE_FILL_LAP_BUDGET + POST_ROLL_LAP_BUDGET_MAX + GAP_LAPS
    max_laps = NUM_CYCLES * per_cycle_laps + 120

    print("AT-2.5: Long-run multi-cycle stability and resource hygiene")
    print(f"  config_dir: {config_dir}")
    print(f"  clips_dir: {clips_dir}")
    print(f"  num_cycles: {NUM_CYCLES}")
    print(f"  pre_roll_seconds: {PRE_ROLL_SECONDS}")
    print(f"  post_roll_seconds: {POST_ROLL_SECONDS}")
    print(f"  pre_fill_lap_budget: {PRE_FILL_LAP_BUDGET}")
    print(f"  post_roll_lap_budget_max (plan): {POST_ROLL_LAP_BUDGET_MAX}")
    print(f"  gap_laps: {GAP_LAPS}")
    print(f"  max_laps: {max_laps}")
    print(f"  max_rss_growth_mb: {MAX_RSS_GROWTH_MB}")
    print(f"  preview: {'enabled' if PREVIEW_ENABLED else 'disabled'}")
    print(f"  verify_tpu: {VERIFY_TPU}")
    print(f"  full_record: {FULL_RECORD}")

    cycle_results: list[CycleResult] = []
    phase = "prefill"
    idle_laps = 0
    gap_laps = 0
    cycle_index = 0
    clips_before_cycle = clips_before_run

    try:
        pipeline = build_pipeline(app_config)
        manager = pipeline.manager

        def should_stop() -> bool:
            nonlocal phase, idle_laps, gap_laps, cycle_index, clips_before_cycle

            if cycle_index >= NUM_CYCLES:
                return True

            if phase == "prefill":
                idle_laps += 1
                if idle_laps > PRE_FILL_LAP_BUDGET:
                    return True
                if _pre_roll_window_full(manager.pre_buffer):
                    _validate_pre_buffer(manager)
                    span = _pre_buffer_time_span(manager.pre_buffer)
                    print(
                        f"\n[cycle {cycle_index + 1}/{NUM_CYCLES}] begin_clip() "
                        f"after {idle_laps} idle lap(s), "
                        f"pre_buffer={len(manager.pre_buffer)} frame(s), "
                        f"span={span:.2f}s ..."
                    )
                    manager.begin_clip()
                    phase = "post"
                return False

            if phase == "post":
                new_clips = _clip_files(clips_dir) - clips_before_cycle
                if new_clips:
                    result = _finish_cycle(
                        manager,
                        cycle_index=cycle_index + 1,
                        clips_before_cycle=clips_before_cycle,
                        clips_dir=clips_dir,
                    )
                    cycle_results.append(result)
                    print(
                        f"  cycle {result.index} OK: {result.clip_path.name} "
                        f"frames={result.frame_count} rss_mb={result.peak_rss_mb:.1f}"
                    )
                    cycle_index += 1
                    if cycle_index >= NUM_CYCLES:
                        return True
                    clips_before_cycle = _clip_files(clips_dir)
                    phase = "gap"
                    gap_laps = 0
                    idle_laps = 0
                elif not manager.clip_active:
                    raise RuntimeError(
                        f"cycle {cycle_index + 1}: clip_active cleared but no new clip file "
                        f"(pre_buffer={len(manager.pre_buffer)}, "
                        f"post_buffer={len(manager.post_buffer)})"
                    )
                return False

            if phase == "gap":
                _assert_idle_state(manager, context=f"cycle {cycle_index} gap")
                _assert_recorder_released(manager, context=f"cycle {cycle_index} gap")
                gap_laps += 1
                if gap_laps >= GAP_LAPS:
                    phase = "prefill"
                return False

            return True

        print(f"\nRunning {NUM_CYCLES} clip cycles (max_laps={max_laps}) ...")
        manager.run_loop(
            max_laps=max_laps,
            should_stop=should_stop,
            full_record=FULL_RECORD,
        )
        post_laps = _post_roll_lap_budget(float(app_config.camera.recommended_fps))

        print(f"  camera recommended_fps: {app_config.camera.recommended_fps:.2f}")
        print(f"  post_roll_lap_budget (measured): {post_laps}")
        print(f"  capture_fps in use: {manager.camera.capture_fps:.2f}")

        if len(cycle_results) != NUM_CYCLES:
            raise RuntimeError(
                f"completed {len(cycle_results)}/{NUM_CYCLES} cycles "
                f"(phase={phase!r}, clip_active={manager.clip_active}, max_laps={max_laps})"
            )

        rss_start = cycle_results[0].peak_rss_mb
        rss_end = cycle_results[-1].peak_rss_mb
        rss_growth = rss_end - rss_start
        if rss_growth > MAX_RSS_GROWTH_MB:
            raise RuntimeError(
                f"peak RSS grew {rss_growth:.1f} MB across cycles "
                f"({rss_start:.1f} -> {rss_end:.1f}), limit {MAX_RSS_GROWTH_MB} MB"
            )

        new_clips_total = _clip_files(clips_dir) - clips_before_run
        print("\nResults:")
        print(f"  cycles_completed: {len(cycle_results)}")
        print(f"  new_event_clips: {len(new_clips_total)}")
        print(f"  peak_rss_first_cycle_mb: {rss_start:.1f}")
        print(f"  peak_rss_last_cycle_mb: {rss_end:.1f}")
        print(f"  peak_rss_growth_mb: {rss_growth:.1f}")
        print(f"  clip_active: {manager.clip_active}")
        print(f"  pre_buffer entries: {len(manager.pre_buffer)}")
        print(f"  post_buffer entries: {len(manager.post_buffer)}")
        for result in cycle_results:
            print(
                f"    cycle {result.index}: {result.clip_path.name} "
                f"frames={result.frame_count} pre_buf={result.pre_buffer_after} "
                f"rss_mb={result.peak_rss_mb:.1f}"
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

    print("\nAT-2.5: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
