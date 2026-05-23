"""
AT-2.3: Post-roll completion boundary precision (integration).

Verifies wall-clock post-roll gating: save must not occur before
``post_roll_seconds`` elapses and must occur once the threshold is reached.
Uses controlled ``time.monotonic()`` values at the boundary.

Usage (from repo root, Pi edge venv with camera, display for preview, optional Coral):

    python src/tests/integration/at_2_3/at_2_3_post_roll_boundary_integration.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

POST_ROLL_SECONDS = 0.5
VERIFY_TPU = True


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths):
    """Preview is always on for AT-2.3."""
    app_config = resolve_runtime_paths(app_config, repo_root)
    recording = app_config.recording_manager
    return replace(
        app_config,
        preview=replace(app_config.preview, enabled=True),
        recording_manager=replace(
            recording,
            post_roll_seconds=POST_ROLL_SECONDS,
        ),
    )


def _run_post_roll_lap(manager, *, monotonic_value: float):
    with patch(
        "netrapi.recording.recording_manager.time.monotonic",
        return_value=monotonic_value,
    ):
        return manager.run_one_lap(full_record=False)


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

    print("AT-2.3: Post-roll completion boundary precision")
    print(f"  config_dir: {config_dir}")
    print(f"  preview enabled: {app_config.preview.enabled} (forced on)")
    print(f"  post_roll_seconds: {POST_ROLL_SECONDS}")

    started_at = 1000.0
    before_threshold = started_at + POST_ROLL_SECONDS - 0.01
    at_threshold = started_at + POST_ROLL_SECONDS

    try:
        pipeline = build_pipeline(app_config, verify_tpu=VERIFY_TPU)
        manager = pipeline.manager
        original_write = manager.recorder.write_clip
        write_calls = {"count": 0}

        def _counting_write(package, *, fps: float):
            write_calls["count"] += 1
            return original_write(package, fps=fps)

        manager.recorder.write_clip = _counting_write  # type: ignore[method-assign]

        manager._camera.open()
        try:
            # Minimal clip_active setup for the wall-clock gate only. Buffers are
            # not sized for coverage (pre_ok/post_ok); that belongs in TP-23.
            manager.begin_clip()
            manager._post_roll_started_at = started_at

            print(f"\nCase A: monotonic={before_threshold:.2f} (threshold - 0.01s) ...")
            result = _run_post_roll_lap(manager, monotonic_value=before_threshold)
            if result is not None:
                raise RuntimeError("Case A: clip saved before post_roll threshold")
            if write_calls["count"] != 0:
                raise RuntimeError("Case A: write_clip called before threshold")
            if not manager.clip_active:
                raise RuntimeError("Case A: clip_active cleared before threshold")
            print("  no save; clip_active still true")

            print(f"\nCase B: monotonic={at_threshold:.2f} (at threshold) ...")
            result = _run_post_roll_lap(manager, monotonic_value=at_threshold)
            if result is None:
                raise RuntimeError("Case B: clip did not save at threshold")
            if write_calls["count"] != 1:
                raise RuntimeError(f"Case B: expected 1 write_clip call, got {write_calls['count']}")
            if manager.clip_active:
                raise RuntimeError("Case B: clip_active still true after save")
            if len(manager.post_buffer) != 0:
                raise RuntimeError("Case B: post_buffer not cleared after save")
            print("  saved once; clip finalized")
        finally:
            manager._camera.close()
            manager.recorder.release()
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    print("\nAT-2.3: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
