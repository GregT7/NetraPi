"""
AT-2.2: Event gate policy matrix — unsafe vs safe (integration).

Verifies clip-start policy with stubbed ``DrivingEvent`` values on a live camera
session: unsafe events always record; safe events only when ``record_safe_events``
is true.

Usage (from repo root, Pi edge venv with camera, display for preview, optional Coral):

    python src/tests/integration/at_2_2/at_2_2_event_gate_policy_matrix_integration.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

POST_ROLL_SECONDS = 0.0
VERIFY_TPU = True


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths, record_safe_events: bool):
    app_config = resolve_runtime_paths(app_config, repo_root)
    recording = app_config.recording_manager
    return replace(
        app_config,
        preview=replace(app_config.preview, enabled=True),
        recording_manager=replace(
            recording,
            post_roll_seconds=POST_ROLL_SECONDS,
            record_safe_events=record_safe_events,
        ),
    )


def _stub_event_manager(event):
    stub = MagicMock()
    stub.evaluate.return_value = event
    return stub


def _run_one_idle_lap(manager) -> None:
    manager._camera.open()
    try:
        manager.run_one_lap(full_record=False)
    finally:
        manager._camera.close()
        manager.recorder.release()


def _assert_clip_state(
    manager,
    *,
    scenario: str,
    expect_clip_active: bool,
) -> None:
    if manager.clip_active is not expect_clip_active:
        raise RuntimeError(
            f"{scenario}: expected clip_active={expect_clip_active}, "
            f"got {manager.clip_active}"
        )


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.events import DrivingEvent, StopSignEnum
    from netrapi.exceptions import NetraPiError

    config_dir = DEFAULT_CONFIG_DIR.resolve()
    base_config = AppConfig.load(config_dir)

    print("AT-2.2: Event gate policy matrix (unsafe vs safe)")
    print(f"  config_dir: {config_dir}")
    print(f"  preview enabled: forced on")
    print(f"  post_roll_seconds: {POST_ROLL_SECONDS}")

    scenarios = [
        (
            "unsafe + record_safe_events=false",
            False,
            DrivingEvent(type=StopSignEnum.ROLLING_STOP),
            True,
        ),
        (
            "safe + record_safe_events=false",
            False,
            DrivingEvent(type=StopSignEnum.COMPLETE_STOP),
            False,
        ),
        (
            "safe + record_safe_events=true",
            True,
            DrivingEvent(type=StopSignEnum.COMPLETE_STOP),
            True,
        ),
        (
            "unsafe + record_safe_events=true",
            True,
            DrivingEvent(type=StopSignEnum.RUN_THROUGH),
            True,
        ),
    ]

    try:
        for label, record_safe, event, expect_clip in scenarios:
            app_config = _apply_test_config(
                base_config,
                repo_root=REPO_ROOT,
                resolve_runtime_paths=_resolve_runtime_paths,
                record_safe_events=record_safe,
            )
            pipeline = build_pipeline(app_config, verify_tpu=VERIFY_TPU)
            manager = pipeline.manager
            manager._event_manager = _stub_event_manager(event)

            print(f"\nScenario: {label} (event={event.type.name}) ...")
            _run_one_idle_lap(manager)
            _assert_clip_state(manager, scenario=label, expect_clip_active=expect_clip)
            print(f"  clip_active={manager.clip_active} (expected {expect_clip})")
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    print("\nAT-2.2: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
