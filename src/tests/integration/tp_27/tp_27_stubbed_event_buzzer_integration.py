"""
TP-27: Audible feedback on unsafe stop-sign events (integration).

Builds the real edge pipeline (including the real ``Buzzer``), mocks the camera,
and injects mock ``DrivingEvent`` values via a stub ``EventManager``. Confirms
``buzzer.beep`` runs for ``ROLLING_STOP`` / ``RUN_THROUGH`` within 10 s of
evaluate, and does not run for ``COMPLETE_STOP`` under default
``play_on.safe=false``.

Does **not** require a USB camera or real stop-sign classification.
Coral USB TPU **is** required at build time: ``build_pipeline`` always calls
``Detector.load()`` on the edgetpu model even though the stub sets
``needs_detection=False`` (no live inference).

Usage (from repo root, Pi edge venv with Coral + buzzer on GPIO 18):

    python src/tests/integration/tp_27/tp_27_stubbed_event_buzzer_integration.py

Skip interactive hear prompts (timing assertion only):

    python src/tests/integration/tp_27/tp_27_stubbed_event_buzzer_integration.py --assume-heard
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[2] / "main" / "edge"

# Max allowed evaluate → beep latency (M-3.31 / TP-27).
MAX_FEEDBACK_LATENCY_S = 10.0
# Laps after arming before failing an expect-beep scenario.
ARMED_LAP_BUDGET = 30
# Laps to run for expect-no-beep (COMPLETE_STOP).
NO_BEEP_LAP_BUDGET = 5
VERIFY_TPU = False
PREVIEW_ENABLED = False
FULL_RECORD = False
# Slightly longer tone so the operator can hear it clearly on the bench.
BEEP_DURATION_SECONDS = 0.5


@dataclass(frozen=True)
class Scenario:
    label: str
    event_type_name: str
    expect_beep: bool


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        label="ROLLING_STOP (expect beep)",
        event_type_name="ROLLING_STOP",
        expect_beep=True,
    ),
    Scenario(
        label="RUN_THROUGH (expect beep)",
        event_type_name="RUN_THROUGH",
        expect_beep=True,
    ),
    Scenario(
        label="COMPLETE_STOP (expect no beep)",
        event_type_name="COMPLETE_STOP",
        expect_beep=False,
    ),
)


class _FakeCamera:
    """Synthetic frames so ``run_loop`` does not need USB capture hardware."""

    def __init__(self, frame: np.ndarray, *, capture_fps: float = 30.0) -> None:
        self._frame = frame
        self.capture_fps = capture_fps

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def read(self) -> np.ndarray:
        return self._frame.copy()

    def measure_fps(self, *, apply: bool = False) -> float:
        if apply:
            self.capture_fps = 30.0
        return self.capture_fps


class _DeferredEventStub:
    """Armed stub: ready_to_evaluate when set; evaluate returns the fixed event.

    ``needs_detection`` is False so the idle lap skips the detector (mock events only).
    """

    def __init__(self) -> None:
        self._event = None

    @property
    def needs_detection(self) -> bool:
        return False

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


@dataclass
class _BeepProbe:
    """Records times only when the real ``Buzzer.beep`` starts a tone."""

    calls: list[tuple[float, str]]

    def track(self, real_beep: Callable) -> Callable:
        def _tracked(event) -> bool:
            started = bool(real_beep(event))
            if started:
                self.calls.append((time.monotonic(), event.type.name))
            return started

        return _tracked


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths: Callable):
    app_config = resolve_runtime_paths(app_config, repo_root)
    buzzer = app_config.buzzer
    app_config = replace(
        app_config,
        buzzer=replace(
            buzzer,
            duration_seconds=BEEP_DURATION_SECONDS,
            play_on=replace(buzzer.play_on, unsafe=True, safe=False),
        ),
        recording_manager=replace(
            app_config.recording_manager,
            # Unsafe events still begin_clip; keep post-roll short — we stop early.
            post_roll_seconds=1.0,
            record_safe_events=False,
        ),
    )
    if not PREVIEW_ENABLED:
        app_config = replace(
            app_config,
            preview=replace(app_config.preview, enabled=False),
        )
    return app_config


def _confirm_heard(scenario: Scenario, *, assume_heard: bool) -> None:
    if assume_heard:
        print("  hear confirmation: skipped (--assume-heard)")
        return
    answer = input("  Did you hear the beep? [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        raise RuntimeError(f"{scenario.label}: operator did not confirm audible feedback")


def _run_scenario(
    *,
    scenario: Scenario,
    base_config,
    repo_root: Path,
    resolve_runtime_paths,
    build_pipeline,
    DrivingEvent,
    StopSignEnum,
    assume_heard: bool,
) -> float | None:
    """Run one stubbed event through the real pipeline. Returns latency_s if beeped."""
    app_config = _apply_test_config(
        base_config,
        repo_root=repo_root,
        resolve_runtime_paths=resolve_runtime_paths,
    )

    pipeline = build_pipeline(app_config, verify_tpu=VERIFY_TPU)
    manager = pipeline.manager

    cam = app_config.camera
    frame = np.zeros((cam.height, cam.width, cam.channels), dtype=np.uint8)
    manager._camera = _FakeCamera(frame, capture_fps=float(cam.recommended_fps))

    # Fail fast: soft-disabled GPIO must not look like a timing PASS.
    manager._buzzer.open()
    if not manager._buzzer.available:
        raise RuntimeError(
            "Buzzer GPIO unavailable (RPi.GPIO / rpi-lgpio missing or pin busy). "
            "In the edge venv run: pip install rpi-lgpio"
        )

    stub = _DeferredEventStub()
    manager._event_manager = stub

    probe = _BeepProbe(calls=[])
    manager._buzzer.beep = probe.track(manager._buzzer.beep)  # type: ignore[method-assign]

    event = DrivingEvent(type=getattr(StopSignEnum, scenario.event_type_name))
    armed_at: float | None = None
    laps_after_arm = 0
    phase = "arm_next"

    def should_stop() -> bool:
        nonlocal phase, armed_at, laps_after_arm
        if phase == "arm_next":
            print(
                f"\n  Arming stub {scenario.event_type_name} — listen for beep ..."
            )
            stub.arm(event)
            armed_at = time.monotonic()
            phase = "armed"
            return False
        if phase == "armed":
            laps_after_arm += 1
            if scenario.expect_beep:
                if probe.calls:
                    # Let the daemon tone finish before teardown.
                    time.sleep(BEEP_DURATION_SECONDS + 0.15)
                    return True
                if laps_after_arm > ARMED_LAP_BUDGET:
                    return True
            else:
                if laps_after_arm >= NO_BEEP_LAP_BUDGET:
                    return True
            return False
        return True

    max_laps = ARMED_LAP_BUDGET + NO_BEEP_LAP_BUDGET + 5
    print(f"\nScenario: {scenario.label}")
    print(f"  gpio_pin={app_config.buzzer.gpio_pin}  "
          f"pitch={app_config.buzzer.pitch:g}Hz  "
          f"volume={app_config.buzzer.volume:g}%  "
          f"duration={app_config.buzzer.duration_seconds:g}s")
    manager.run_loop(
        max_laps=max_laps,
        should_stop=should_stop,
        full_record=FULL_RECORD,
    )

    if armed_at is None:
        raise RuntimeError(f"{scenario.label}: stub never armed")

    if scenario.expect_beep:
        if not probe.calls:
            raise RuntimeError(
                f"{scenario.label}: expected buzzer.beep, got 0 calls "
                f"(laps_after_arm={laps_after_arm})"
            )
        beep_at, beep_type = probe.calls[0]
        if beep_type != scenario.event_type_name:
            raise RuntimeError(
                f"{scenario.label}: beep type {beep_type!r} != {scenario.event_type_name!r}"
            )
        latency_s = beep_at - armed_at
        print(f"  evaluate→beep latency: {latency_s * 1000:.1f} ms "
              f"({latency_s:.3f}s; limit {MAX_FEEDBACK_LATENCY_S:g}s)")
        if latency_s > MAX_FEEDBACK_LATENCY_S:
            raise RuntimeError(
                f"{scenario.label}: feedback latency {latency_s:.3f}s "
                f"> {MAX_FEEDBACK_LATENCY_S:g}s"
            )
        _confirm_heard(scenario, assume_heard=assume_heard)
        return latency_s

    if probe.calls:
        types = ", ".join(t for _, t in probe.calls)
        raise RuntimeError(
            f"{scenario.label}: unexpected beep call(s): {types} "
            f"(play_on.safe should be false)"
        )
    print(f"  no beep after {laps_after_arm} lap(s) (ok)")
    return None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TP-27 stubbed-event buzzer integration")
    parser.add_argument(
        "--assume-heard",
        action="store_true",
        help="Skip interactive operator confirmation that the beep was audible",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
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

    print("TP-27: Stubbed event → real buzzer (unsafe audible feedback)")
    print(f"  config_dir: {config_dir}")
    print(f"  max_feedback_latency_s: {MAX_FEEDBACK_LATENCY_S}")
    print(f"  camera: mocked (_FakeCamera)")
    print(f"  preview: {'enabled' if PREVIEW_ENABLED else 'disabled'}")
    print(f"  verify_tpu: {VERIFY_TPU}")
    print(f"  assume_heard: {args.assume_heard}")
    print(f"  scenarios: {len(SCENARIOS)}")

    latencies: list[tuple[str, float]] = []

    try:
        for scenario in SCENARIOS:
            latency = _run_scenario(
                scenario=scenario,
                base_config=base_config,
                repo_root=REPO_ROOT,
                resolve_runtime_paths=_resolve_runtime_paths,
                build_pipeline=build_pipeline,
                DrivingEvent=DrivingEvent,
                StopSignEnum=StopSignEnum,
                assume_heard=args.assume_heard,
            )
            if latency is not None:
                latencies.append((scenario.label, latency))
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
    for label, latency in latencies:
        print(f"  [{label}] latency={latency * 1000:.1f} ms")
    print(f"  no-beep scenarios: {sum(1 for s in SCENARIOS if not s.expect_beep)}")
    print("\nTP-27: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
