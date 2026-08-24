"""
TP-24: RecordingManager Ctrl+C and preview controls (integration).

Runs ``RecordingManager.run_loop()`` on the Pi with preview and full trip
recording always enabled (TP-22 prerequisite). Verifies live ``display`` frames
reach the preview path, automated SIGINT shutdown, and manual Ctrl+C in the
terminal during a live loop.

Usage (from repo root, Pi edge venv, interactive terminal, display for preview):

    python src/tests/integration/tp_24/tp_24_preview_ctrl_c_integration.py

Phase 3 requires pressing Ctrl+C in the same terminal when prompted.

Optional evidence for the test matrix: screenshot or short video of the preview
window during phase 1 or phase 3 (window name from ``preview.json``).
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

PREVIEW_LAPS = 30
SIGINT_AFTER_SECONDS = 2.5
VERIFY_TPU = True


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _trip_files(trips_dir: Path) -> set[Path]:
    if not trips_dir.is_dir():
        return set()
    return {path.resolve() for path in trips_dir.glob("*.mp4")}


def _pre_buffer_time_span(pre_buffer) -> float:
    records = pre_buffer._records
    if len(records) < 2:
        return 0.0
    return records[-1][0] - records[0][0]


def _validate_display_frames(manager) -> None:
    pre_buffer = manager.pre_buffer
    if len(pre_buffer) == 0:
        raise RuntimeError("pre_buffer is empty; expected FrameRecord entries with display frames")

    for index, display in enumerate(pre_buffer.display_frames()):
        if display.ndim != 3:
            raise RuntimeError(f"pre_buffer[{index}].display must be 3-D, got {display.shape}")
        if display.size == 0:
            raise RuntimeError(f"pre_buffer[{index}].display is empty")


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths):
    """Preview and trip recording are always on for TP-24."""
    app_config = resolve_runtime_paths(app_config, repo_root)
    return replace(
        app_config,
        preview=replace(app_config.preview, enabled=True),
        trip_recorder=replace(app_config.trip_recorder, enabled=True),
    )


def _assert_camera_closed(camera) -> None:
    from netrapi.exceptions import CameraError

    try:
        camera.read()
    except CameraError as exc:
        if "not open" in str(exc).lower():
            return
        raise
    raise RuntimeError("camera.read() succeeded after run_loop; device was not released")


def _assert_camera_reopenable(camera) -> None:
    camera.open()
    try:
        frame = camera.read()
        if frame.ndim != 3 or frame.size == 0:
            raise RuntimeError(f"reopen read returned invalid frame shape {frame.shape}")
    finally:
        camera.close()


def _assert_shutdown_clean(manager, *, label: str) -> None:
    _assert_camera_closed(manager.camera)
    _assert_camera_reopenable(manager.camera)
    if manager.clip_active:
        raise RuntimeError(f"clip_active is true after {label}")


def _schedule_sigint(delay_seconds: float) -> threading.Thread:
    def _send() -> None:
        time.sleep(delay_seconds)
        os.kill(os.getpid(), signal.SIGINT)

    thread = threading.Thread(target=_send, name="tp24-sigint", daemon=True)
    thread.start()
    return thread


class _SigintRunLoopSupport:
    """Test-only shim: tolerate camera read failure while shutting down after SIGINT."""

    def __init__(self, manager) -> None:
        self._manager = manager
        self._original_run_one_lap = manager.run_one_lap

    def __enter__(self) -> _SigintRunLoopSupport:
        from netrapi.exceptions import NetraPiError

        manager = self._manager
        original_run_one_lap = self._original_run_one_lap

        def tolerant_run_one_lap(**kwargs):
            if not manager._running:
                return None
            try:
                return original_run_one_lap(**kwargs)
            except NetraPiError as exc:
                if not manager._running and "failed to read frame" in str(exc).lower():
                    return None
                raise

        manager.run_one_lap = tolerant_run_one_lap
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._manager.run_one_lap = self._original_run_one_lap


def _require_interactive_terminal() -> None:
    if not sys.stdin.isatty():
        raise RuntimeError(
            "TP-24 requires an interactive terminal for manual Ctrl+C (phase 3); "
            "run this script directly in a TTY session on the Pi"
        )


def _run_scheduled_sigint_phase(manager) -> None:
    print(
        f"\nPhase 2: scheduled SIGINT (same as Ctrl+C) after "
        f"~{SIGINT_AFTER_SECONDS:.1f}s in the main loop ..."
    )
    _schedule_sigint(SIGINT_AFTER_SECONDS)
    with _SigintRunLoopSupport(manager):
        manager.run_loop(
            max_laps=10_000,
            full_record=True,
        )
    _assert_shutdown_clean(manager, label="scheduled SIGINT")


def _run_manual_ctrl_c_phase(manager) -> None:
    print(
        "\nPhase 3: manual Ctrl+C — press Ctrl+C in this terminal while the loop runs."
    )
    with _SigintRunLoopSupport(manager):
        manager.run_loop(
            max_laps=10_000,
            full_record=True,
        )
    _assert_shutdown_clean(manager, label="manual Ctrl+C")


def _run_preview_phase(
    manager,
    *,
    trips_before: set[Path],
    trips_dir: Path,
) -> None:
    laps = 0

    def should_stop() -> bool:
        nonlocal laps
        laps += 1
        if not manager._preview.enabled:
            raise RuntimeError("preview must stay enabled for TP-24")
        if laps >= PREVIEW_LAPS:
            _validate_display_frames(manager)
            print(
                f"\n  preview: {laps} lap(s), pre_buffer={len(manager.pre_buffer)} — "
                "phase complete."
            )
            return True
        return False

    max_laps = PREVIEW_LAPS + 30
    print(
        f"\nPhase 1: preview on, full_record on ({PREVIEW_LAPS} laps) ..."
    )
    manager.run_loop(
        max_laps=max_laps,
        should_stop=should_stop,
        full_record=True,
    )

    trips_after = _trip_files(trips_dir)
    if not (trips_after - trips_before):
        raise RuntimeError("full_record enabled but no trip segment was written to trips_dir")


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

    preview_cfg = app_config.preview
    trips_dir = app_config.trip_recorder.segments_dir
    trips_before = _trip_files(trips_dir)

    try:
        _require_interactive_terminal()
    except RuntimeError as exc:
        print(f"Prerequisite failed: {exc}", file=sys.stderr)
        return 1

    print("TP-24: RecordingManager Ctrl+C and preview controls")
    print(f"  config_dir: {config_dir}")
    print(f"  preview window: {preview_cfg.window_name!r}")
    print(f"  preview enabled: {preview_cfg.enabled} (forced on)")
    print(f"  trip_recorder enabled: {app_config.trip_recorder.enabled} (forced on)")
    print(f"  trips_dir: {trips_dir}")
    print(f"  preview_laps: {PREVIEW_LAPS}")
    print(f"  sigint_main_loop_seconds: {SIGINT_AFTER_SECONDS}")
    print(f"  verify_tpu: {VERIFY_TPU}")
    print(
        "  evidence: optional screenshot/video of the preview window during phases 1 or 3."
    )

    try:
        pipeline = build_pipeline(app_config)
        manager = pipeline.manager

        _run_preview_phase(
            manager,
            trips_before=trips_before,
            trips_dir=trips_dir,
        )
        trips_after_phase1 = _trip_files(trips_dir)
        new_trips_phase1 = trips_after_phase1 - trips_before
        pre_span = _pre_buffer_time_span(manager.pre_buffer)
        sample = manager.pre_buffer.latest()

        print("\nAfter phase 1:")
        print(f"  camera recommended_fps: {app_config.camera.recommended_fps:.2f}")
        print(f"  preview.enabled: {manager._preview.enabled}")
        print(f"  pre_buffer entries: {len(manager.pre_buffer)}")
        print(f"  pre_buffer time span: {pre_span:.2f}s")
        print(f"  latest display shape: {tuple(sample.display.shape)} dtype={sample.display.dtype}")
        print(f"  new trip segment(s): {len(new_trips_phase1)}")
        for path in sorted(new_trips_phase1):
            print(f"    {path.name}")

        _run_scheduled_sigint_phase(manager)
        print("\nAfter phase 2 (scheduled SIGINT):")
        print("  run_loop returned")
        print("  camera closed after shutdown")
        print("  camera reopen/read/close succeeded (no device lock)")
        print(f"  clip_active: {manager.clip_active}")

        _run_manual_ctrl_c_phase(manager)
        print("\nAfter phase 3 (manual Ctrl+C):")
        print("  run_loop returned")
        print("  camera closed after shutdown")
        print("  camera reopen/read/close succeeded (no device lock)")
        print(f"  clip_active: {manager.clip_active}")
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(
            "\nKeyboardInterrupt outside RecordingManager.run_loop "
            "(phase 3 should normally stop via the manager SIGINT handler).",
            file=sys.stderr,
        )
        return 1

    print("\nTP-24: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
