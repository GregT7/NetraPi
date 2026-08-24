"""
AT-7.2: Real camera + SPACE-armed stubbed events → deployed cloud.

Dry-run before live AT-7.3: same three SPACE-armed phases as TP-28 / AT-7.3
(complete stop → rolling stop → run-through) with **real camera + preview**,
but EventManager is stubbed so SPACE injects the intended event. Persist and
upload still go through RecordingManager / LocalStore / CloudIngest.

Usage (from repo root, Pi — camera + Coral + buzzer on BCM 18):

    python src/tests/integration/at_7_2/at_7_2_camera_stubbed_events_deployed_cloud.py

1. Click the preview window for focus.
2. When prompted, press SPACE to arm; the stub fires that phase's event.
3. Confirm beep/clip for unsafe phases only, then local s3_stored flags.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

SCRIPT_DIR = Path(__file__).resolve().parent
INTEGRATION_DIR = SCRIPT_DIR.parent
MAIN_DIR = SCRIPT_DIR.parents[2] / "main"
EDGE_DIR = MAIN_DIR / "edge"
OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"

MAX_FEEDBACK_LATENCY_S = 10.0
ENCOUNTER_TIMEOUT_S = 60.0
CLIP_WAIT_BUDGET_S = 60.0
SAFE_SETTLE_S = 2.0
PRE_ROLL_SECONDS = 2.0
POST_ROLL_SECONDS = 2.0
VERIFY_TPU = False
FULL_RECORD = False
BEEP_DURATION_SECONDS = 0.5
BEEP_VOLUME_PERCENT = 80.0
PREVIEW_MAX_WIDTH = 1280
PREVIEW_MAX_HEIGHT = 720
CLIPS_SUBDIR = "at_7_2"
EXPECTED_CLOUD_TYPES = ("complete-stop", "rolling-stop", "run-through")
TYPES_EXPECT_CLIP_UPLOAD = frozenset({"rolling-stop", "run-through"})


@dataclass(frozen=True)
class Scenario:
    label: str
    event_type_name: str
    expect_beep: bool
    expect_clip: bool


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        label="1/3 Complete stop (stubbed)",
        event_type_name="COMPLETE_STOP",
        expect_beep=False,
        expect_clip=False,
    ),
    Scenario(
        label="2/3 Rolling stop (stubbed)",
        event_type_name="ROLLING_STOP",
        expect_beep=True,
        expect_clip=True,
    ),
    Scenario(
        label="3/3 Run-through (stubbed)",
        event_type_name="RUN_THROUGH",
        expect_beep=True,
        expect_clip=True,
    ),
)


@dataclass
class LoggedEvent:
    type_name: str
    evaluated_at: float
    is_unsafe: bool


@dataclass
class EncounterResult:
    scenario: Scenario
    classified_as: str
    latency_s: float | None
    clip_path: Path | None


@dataclass
class _Session:
    lock: threading.Lock = field(default_factory=threading.Lock)
    phase: str = "boot"  # boot | prompt | armed | observed | waiting_clip | between
    observed: LoggedEvent | None = None
    clip_path: Path | None = None
    allow_side_effects: bool = False
    stop_requested: bool = False
    fatal: str | None = None
    arm_event: threading.Event = field(default_factory=threading.Event)
    claim_at: float | None = None


@dataclass
class _BeepProbe:
    calls: list[tuple[float, str]]
    play_on_unsafe: bool = True
    play_on_safe: bool = False

    def track(self, real_beep: Callable) -> Callable:
        def _tracked(event) -> None:
            if event.is_unsafe:
                will_play = self.play_on_unsafe
            else:
                will_play = self.play_on_safe
            if will_play:
                self.calls.append((time.monotonic(), event.type.name))
            real_beep(event)

        return _tracked


class _DeferredEventStub:
    """Armed stub: ready_to_evaluate when set; evaluate returns the fixed event."""

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


def _configure_import_path() -> None:
    for path in (MAIN_DIR, EDGE_DIR, INTEGRATION_DIR):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def _clip_files(clips_dir: Path) -> set[Path]:
    if not clips_dir.is_dir():
        return set()
    return {path.resolve() for path in clips_dir.glob("*.mp4")}


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


def _apply_test_config(
    app_config,
    *,
    repo_root: Path,
    resolve_runtime_paths: Callable,
    clips_dir: Path,
):
    app_config = resolve_runtime_paths(app_config, repo_root)
    buzzer = app_config.buzzer
    recording = app_config.recording_manager
    return replace(
        app_config,
        buzzer=replace(
            buzzer,
            duration_seconds=BEEP_DURATION_SECONDS,
            volume=BEEP_VOLUME_PERCENT,
            play_on=replace(buzzer.play_on, unsafe=True, safe=False),
        ),
        recording_manager=replace(
            recording,
            record_safe_events=False,
            clips_dir=clips_dir,
            pre_roll_seconds=PRE_ROLL_SECONDS,
            post_roll_seconds=POST_ROLL_SECONDS,
        ),
        preview=replace(
            app_config.preview,
            enabled=True,
            max_width=PREVIEW_MAX_WIDTH,
            max_height=PREVIEW_MAX_HEIGHT,
        ),
    )


def _stub_event(StopSignEnum, DrivingEvent, ApproachSnapshot, event_type_name: str):
    event_type = getattr(StopSignEnum, event_type_name)
    return DrivingEvent(
        type=event_type,
        knn_stage1=(0.4, 0.12, 0.9, 0.08),
        knn_stage2=(0.12, 4.2),
        approach=ApproachSnapshot(
            peak_area_pct=1.1,
            approach_duration_s=1.8,
            increasing_fraction=0.7,
            log_linear_r2=0.85,
            drop_duration_s=0.4,
            post_drop_holds=False,
            fail_reasons=(),
        ),
    )


def _install_preview_helpers(manager, *, session: _Session) -> None:
    import cv2

    preview = manager._preview
    real_show = preview.show

    def fit_scale_to_max(frame):
        height, width = frame.shape[:2]
        max_width = preview.config.max_width
        max_height = preview.config.max_height
        scale = min(max_width / width, max_height / height)
        if abs(scale - 1.0) < 1e-6:
            return frame
        new_width = max(1, int(round(width * scale)))
        new_height = max(1, int(round(height * scale)))
        interpolation = cv2.INTER_LINEAR if scale > 1.0 else cv2.INTER_AREA
        return cv2.resize(frame, (new_width, new_height), interpolation=interpolation)

    def show_with_arm(frame):
        key = real_show(frame)
        if key == ord(" "):
            with session.lock:
                if session.phase == "prompt":
                    session.arm_event.set()
        return key

    preview._fit_frame = fit_scale_to_max  # type: ignore[method-assign]
    preview.show = show_with_arm  # type: ignore[method-assign]


def _wait_for_space(*, session: _Session) -> None:
    session.arm_event.clear()
    print(
        "  Click preview for focus, then press SPACE to fire the stubbed event.\n"
        "  (Nothing is injected before SPACE — no beep/clip.)",
        flush=True,
    )
    while True:
        if session.arm_event.wait(timeout=0.25):
            return
        with session.lock:
            if session.fatal or session.stop_requested:
                raise RuntimeError("stopped while waiting to arm")


def _wait_pre_roll(*, manager, session: _Session, timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with session.lock:
            if session.fatal or session.stop_requested:
                raise RuntimeError("stopped while filling pre-roll")
        if _pre_roll_window_full(manager.pre_buffer):
            return
        time.sleep(0.05)
    raise RuntimeError(
        f"pre-roll window not full within {timeout_s:g}s "
        f"(span={_pre_buffer_time_span(manager.pre_buffer):.2f}s)"
    )


def _operator_thread(
    *,
    session: _Session,
    manager,
    stub: _DeferredEventStub,
    StopSignEnum,
    DrivingEvent,
    ApproachSnapshot,
    clips_dir: Path,
    clips_before: set[Path],
    probe: _BeepProbe,
    results: list[EncounterResult],
) -> None:
    try:
        for scenario in SCENARIOS:
            with session.lock:
                session.phase = "prompt"
                session.observed = None
                session.clip_path = None
                session.claim_at = None
                session.allow_side_effects = False
                probe.calls.clear()
            stub.clear()

            print("\n" + "=" * 60, flush=True)
            print(f"Phase: {scenario.label}", flush=True)
            print(
                f"  Stub will inject: {scenario.event_type_name}",
                flush=True,
            )
            _wait_for_space(session=session)
            _wait_pre_roll(manager=manager, session=session)
            stub.arm(
                _stub_event(
                    StopSignEnum,
                    DrivingEvent,
                    ApproachSnapshot,
                    scenario.event_type_name,
                )
            )
            with session.lock:
                session.phase = "armed"
            print(
                f"  Armed stub ({scenario.event_type_name}). "
                f"Waiting up to {ENCOUNTER_TIMEOUT_S:g}s ...",
                flush=True,
            )

            deadline = time.monotonic() + ENCOUNTER_TIMEOUT_S
            observed: LoggedEvent | None = None
            while time.monotonic() < deadline:
                with session.lock:
                    if session.fatal:
                        return
                    if session.observed is not None:
                        observed = session.observed
                        break
                time.sleep(0.05)
            else:
                raise RuntimeError(
                    f"{scenario.label}: stub event not evaluated within "
                    f"{ENCOUNTER_TIMEOUT_S:g}s"
                )

            assert observed is not None
            print(
                f"  Evaluated: {observed.type_name} "
                f"(intended {scenario.event_type_name})",
                flush=True,
            )
            if observed.type_name != scenario.event_type_name:
                raise RuntimeError(
                    f"{scenario.label}: got {observed.type_name!r} "
                    f"!= intended {scenario.event_type_name!r}"
                )

            latency_s: float | None = None
            if scenario.expect_beep:
                beep_deadline = observed.evaluated_at + MAX_FEEDBACK_LATENCY_S
                while time.monotonic() < beep_deadline and not probe.calls:
                    time.sleep(0.02)
                if not probe.calls:
                    raise RuntimeError(
                        f"{scenario.label}: expected buzzer within "
                        f"{MAX_FEEDBACK_LATENCY_S:g}s of evaluate"
                    )
                beep_at, beep_type = probe.calls[0]
                if beep_type != scenario.event_type_name:
                    raise RuntimeError(
                        f"{scenario.label}: beep type {beep_type!r} "
                        f"!= {scenario.event_type_name!r}"
                    )
                latency_s = beep_at - observed.evaluated_at
                print(
                    f"  evaluate→beep: {latency_s * 1000:.1f} ms "
                    f"(limit {MAX_FEEDBACK_LATENCY_S:g}s)",
                    flush=True,
                )
                if latency_s > MAX_FEEDBACK_LATENCY_S:
                    raise RuntimeError(
                        f"{scenario.label}: feedback latency {latency_s:.3f}s "
                        f"> {MAX_FEEDBACK_LATENCY_S:g}s"
                    )
            else:
                time.sleep(SAFE_SETTLE_S)
                if probe.calls:
                    types = ", ".join(t for _, t in probe.calls)
                    raise RuntimeError(
                        f"{scenario.label}: unexpected beep(s): {types}"
                    )
                print("  no beep (ok)", flush=True)

            clip_path: Path | None = None
            if scenario.expect_clip:
                with session.lock:
                    session.phase = "waiting_clip"
                clip_deadline = time.monotonic() + CLIP_WAIT_BUDGET_S
                while time.monotonic() < clip_deadline:
                    with session.lock:
                        probed = session.clip_path
                    if probed is not None:
                        probed = probed.resolve()
                        if probed not in clips_before:
                            clip_path = probed
                            break
                    new_clips = _clip_files(clips_dir) - clips_before
                    if new_clips:
                        clip_path = max(new_clips, key=lambda p: p.stat().st_mtime)
                        break
                    time.sleep(0.1)
                if clip_path is None:
                    raise RuntimeError(
                        f"{scenario.label}: expected a *new* evidence MP4 under "
                        f"{clips_dir}"
                    )
                clips_before.add(clip_path.resolve())
                with session.lock:
                    session.clip_path = None
                print(f"  clip: {clip_path}", flush=True)
            else:
                time.sleep(SAFE_SETTLE_S)
                new_clips = _clip_files(clips_dir) - clips_before
                if new_clips:
                    raise RuntimeError(
                        f"{scenario.label}: unexpected clip(s): "
                        + ", ".join(str(p.name) for p in sorted(new_clips))
                    )
                print("  no clip (ok)", flush=True)

            results.append(
                EncounterResult(
                    scenario=scenario,
                    classified_as=observed.type_name,
                    latency_s=latency_s,
                    clip_path=clip_path,
                )
            )
            with session.lock:
                session.phase = "between"
                session.allow_side_effects = False

        with session.lock:
            session.stop_requested = True
    except Exception as exc:
        with session.lock:
            session.fatal = str(exc)
            session.stop_requested = True


def _install_probes(
    manager,
    *,
    session: _Session,
    probe: _BeepProbe,
) -> None:
    real_evaluate = manager.event_manager.evaluate
    real_finish = manager._finish_clip
    real_begin_clip = manager.begin_clip
    real_commit = manager._commit_evaluated_event
    tracked_beep = probe.track(manager.buzzer.beep)

    def tracked_evaluate():
        event = real_evaluate()
        now = time.monotonic()
        with session.lock:
            if session.phase == "armed" and session.observed is None:
                session.observed = LoggedEvent(
                    type_name=event.type.name,
                    evaluated_at=now,
                    is_unsafe=event.is_unsafe,
                )
                session.phase = "observed"
                session.allow_side_effects = True
                session.claim_at = now
                session.clip_path = None
                print(
                    f"\n  [pipeline] evaluate → {event.type.name} "
                    f"(unsafe={event.is_unsafe})",
                    flush=True,
                )
            else:
                session.allow_side_effects = False
                print(
                    f"\n  [pipeline] evaluate → {event.type.name} "
                    f"(ignored — not armed; no beep/clip/persist)",
                    flush=True,
                )
        return event

    def gated_beep(event) -> None:
        with session.lock:
            allow = session.allow_side_effects
        if allow:
            tracked_beep(event)

    def gated_begin_clip() -> None:
        with session.lock:
            allow = session.allow_side_effects
        if allow:
            real_begin_clip()

    def gated_commit(event) -> None:
        with session.lock:
            allow = session.allow_side_effects
        if allow:
            real_commit(event)

    def tracked_finish_clip():
        result = real_finish()
        with session.lock:
            session.clip_path = Path(result.clip_path).resolve()
        print(f"  [pipeline] wrote clip → {result.clip_path}", flush=True)
        return result

    manager.event_manager.evaluate = tracked_evaluate  # type: ignore[method-assign]
    manager._finish_clip = tracked_finish_clip  # type: ignore[method-assign]
    manager.buzzer.beep = gated_beep  # type: ignore[method-assign]
    manager.begin_clip = gated_begin_clip  # type: ignore[method-assign]
    manager._commit_evaluated_event = gated_commit  # type: ignore[method-assign]


def _inspect_session_uploads(session_id: int) -> list[tuple[int, str, str | None]]:
    from sqlmodel import select

    from db.database import get_session
    from db.models import Classification, ClassificationType, Clip, Event

    rows: list[tuple[int, str, str | None]] = []
    with get_session() as local:
        events = local.exec(
            select(Event)
            .where(Event.driving_session_id == session_id)
            .order_by(Event.id)
        ).all()
        for event in events:
            if event.id is None:
                continue
            classification = local.exec(
                select(Classification).where(
                    Classification.event_id == event.id,
                    Classification.kind == "auto",
                )
            ).first()
            if classification is None:
                raise RuntimeError(f"auto classification missing for event {event.id}")
            type_row = local.get(ClassificationType, classification.classification_type_id)
            if type_row is None:
                raise RuntimeError(f"classification_type missing for event {event.id}")
            clip = local.exec(select(Clip).where(Clip.event_id == event.id)).first()
            if type_row.value in TYPES_EXPECT_CLIP_UPLOAD:
                if clip is None:
                    raise RuntimeError(f"clip missing for event {event.id}")
                if clip.s3_stored is not True or not clip.s3_key:
                    raise RuntimeError(
                        f"event {event.id} ({type_row.value}) not uploaded "
                        f"(s3_stored={clip.s3_stored!r} s3_key={clip.s3_key!r})"
                    )
                rows.append((event.id, type_row.value, clip.s3_key))
            else:
                if clip is not None and clip.init_local_stored and clip.local_path:
                    raise RuntimeError(
                        f"event {event.id} ({type_row.value}) unexpectedly has a "
                        f"stored clip at {clip.local_path!r}"
                    )
                rows.append((event.id, type_row.value, None))
    return rows


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.backend_auth import apply_edge_env, clear_ingest_auth
    from netrapi.events import DrivingEvent, StopSignEnum
    from netrapi.events.driving_event import ApproachSnapshot
    from netrapi.exceptions import NetraPiError

    from _render import api_origin, init_sqlite, sqlite_url, wait_health

    config_dir = DEFAULT_CONFIG_DIR.resolve()

    try:
        apply_edge_env()
        clear_ingest_auth()
        origin = api_origin()
        print("AT-7.2: Camera + SPACE + stubbed events → deployed cloud", flush=True)
        print(f"  origin: {origin}", flush=True)
        wait_health(origin)

        if OUTPUT_DB_PATH.exists():
            OUTPUT_DB_PATH.unlink()
        url = sqlite_url(OUTPUT_DB_PATH)
        os.environ["DATABASE_URL"] = url
        init_sqlite(url)

        base_config = AppConfig.load(config_dir)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    resolved = _resolve_runtime_paths(base_config, REPO_ROOT)
    clips_dir = (resolved.recording_manager.clips_dir / CLIPS_SUBDIR).resolve()
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips_before = _clip_files(clips_dir)

    app_config = _apply_test_config(
        base_config,
        repo_root=REPO_ROOT,
        resolve_runtime_paths=_resolve_runtime_paths,
        clips_dir=clips_dir,
    )

    print("  camera: live USB / Picam")
    print("  EventManager: stubbed (SPACE injects the phase event)")
    print("  persist + ingest: RecordingManager / LocalStore / CloudIngest")
    print(f"  sqlite: {OUTPUT_DB_PATH}")
    print(f"  clips_dir: {clips_dir}")
    print(f"  phases: {', '.join(s.event_type_name for s in SCENARIOS)}")
    print(
        f"  buzzer BCM {app_config.buzzer.gpio_pin}  "
        f"{app_config.buzzer.pitch:g}Hz @ {app_config.buzzer.volume:g}%"
    )
    print(
        f"  rolls: pre={app_config.recording_manager.pre_roll_seconds:g}s  "
        f"post={app_config.recording_manager.post_roll_seconds:g}s"
    )
    print(
        f"  preview ≤{PREVIEW_MAX_WIDTH}x{PREVIEW_MAX_HEIGHT} — "
        "SPACE to fire each stubbed phase"
    )
    print("\nCtrl+C aborts. Camera + Coral + buzzer required (events are stubbed).")

    session = _Session()
    probe = _BeepProbe(
        calls=[],
        play_on_unsafe=app_config.buzzer.play_on.unsafe,
        play_on_safe=app_config.buzzer.play_on.safe,
    )
    results: list[EncounterResult] = []

    try:
        pipeline = build_pipeline(app_config)
        manager = pipeline.manager
        if manager._local_store is None:
            raise RuntimeError(
                "LocalStore not wired; init_sqlite/init_engine must run before build_pipeline"
            )
        if manager._cloud_ingest is None:
            raise RuntimeError(
                "CloudIngest not wired; set NETRAPI_API_URL and NETRAPI_API_KEY in "
                "src/main/edge/.env"
            )

        stub = _DeferredEventStub()
        manager._event_manager = stub
        _install_probes(manager, session=session, probe=probe)
        _install_preview_helpers(manager, session=session)

        manager._buzzer.open()
        if not manager._buzzer.available:
            raise RuntimeError(
                "Buzzer GPIO unavailable (RPi.GPIO / rpi-lgpio missing or pin busy)."
            )

        worker = threading.Thread(
            target=_operator_thread,
            name="at72-operator",
            kwargs={
                "session": session,
                "manager": manager,
                "stub": stub,
                "StopSignEnum": StopSignEnum,
                "DrivingEvent": DrivingEvent,
                "ApproachSnapshot": ApproachSnapshot,
                "clips_dir": clips_dir,
                "clips_before": clips_before,
                "probe": probe,
                "results": results,
            },
            daemon=True,
        )
        worker.start()

        def should_stop() -> bool:
            with session.lock:
                return session.stop_requested

        print("\nPipeline running. Follow the three phase prompts.")
        manager.run_loop(
            should_stop=should_stop,
            full_record=FULL_RECORD,
        )
        worker.join(timeout=5.0)

        with session.lock:
            if session.fatal:
                raise RuntimeError(session.fatal)

        if len(results) != len(SCENARIOS):
            raise RuntimeError(
                f"expected {len(SCENARIOS)} phases, got {len(results)}"
            )

        driving_session_id = manager._driving_session_id
        if driving_session_id is None:
            raise RuntimeError("driving_session_id missing after run_loop")
        uploaded = _inspect_session_uploads(driving_session_id)
        got_types = tuple(type_value for _, type_value, _ in uploaded)
        if got_types != EXPECTED_CLOUD_TYPES:
            raise RuntimeError(
                f"cloud types {got_types!r} != {EXPECTED_CLOUD_TYPES!r}"
            )
        for event_id, type_value, s3_key in uploaded:
            if s3_key is None:
                print(f"  sqlite event {event_id} ({type_value}) -> metadata only")
            else:
                print(f"  sqlite event {event_id} ({type_value}) -> {s3_key}")
        clear_ingest_auth()
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
    for item in results:
        latency = (
            f"{item.latency_s * 1000:.1f} ms"
            if item.latency_s is not None
            else "n/a"
        )
        clip = item.clip_path.name if item.clip_path else "none"
        print(
            f"  [{item.scenario.event_type_name}] evaluated={item.classified_as}  "
            f"latency={latency}  clip={clip}"
        )
    print("\nAT-7.2: PASS")
    print(f"  inspect sqlite: {OUTPUT_DB_PATH}")
    print("  next: AT-7.3 (live classify in car)")
    print("  optional Postgres/S3: see AT-7.1 README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
