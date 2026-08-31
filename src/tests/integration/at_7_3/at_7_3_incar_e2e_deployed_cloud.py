"""
AT-7.3: In-car three-maneuver E2E to deployed cloud.

Same SPACE-armed phases as TP-28 (complete stop → rolling stop → run-through)
on the real pipeline (camera, Detector, EventManager, Buzzer, Recorder).
LocalStore + CloudIngest are the production persist/upload path.

Usage (from repo root, Pi in car — camera + Coral + buzzer on BCM 18):

    python src/tests/integration/at_7_3/at_7_3_incar_e2e_deployed_cloud.py

1. Click the preview window for focus.
2. When prompted, press SPACE to arm, then perform that maneuver at a stop sign.
3. Classifications before SPACE are ignored (no beep / no clip).
"""

from __future__ import annotations

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
SQLITE_PATH = MAIN_DIR / "db" / "netrapi.db"

MAX_FEEDBACK_LATENCY_S = 10.0
ENCOUNTER_TIMEOUT_S = 180.0
CLIP_WAIT_BUDGET_S = 60.0
SAFE_SETTLE_S = 2.0
VERIFY_TPU = True
FULL_RECORD = False
BEEP_DURATION_SECONDS = 0.5
BEEP_VOLUME_PERCENT = 80.0
PREVIEW_MAX_WIDTH = 1280
PREVIEW_MAX_HEIGHT = 720
CLIPS_SUBDIR = "at_7_3"
EXPECTED_CLOUD_TYPES = ("complete-stop", "rolling-stop", "run-through")
TYPES_EXPECT_CLIP_UPLOAD = frozenset({"rolling-stop", "run-through"})


@dataclass(frozen=True)
class Scenario:
    label: str
    event_type_name: str
    expect_beep: bool
    expect_clip: bool


# Fixed drive plan (AT-3.4-style phases 2–4).
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        label="1/3 Complete stop",
        event_type_name="COMPLETE_STOP",
        expect_beep=False,
        expect_clip=False,
    ),
    Scenario(
        label="2/3 Rolling stop",
        event_type_name="ROLLING_STOP",
        expect_beep=True,
        expect_clip=True,
    ),
    Scenario(
        label="3/3 Run-through",
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
    # Monotonic time of the evaluate that claimed this armed encounter (for clip freshness).
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


def _configure_import_path() -> None:
    for path in (MAIN_DIR, EDGE_DIR, INTEGRATION_DIR):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def _clip_files(clips_dir: Path) -> set[Path]:
    if not clips_dir.is_dir():
        return set()
    return {path.resolve() for path in clips_dir.rglob("*.mp4")}


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
        ),
        preview=replace(
            app_config.preview,
            enabled=True,
            max_width=PREVIEW_MAX_WIDTH,
            max_height=PREVIEW_MAX_HEIGHT,
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
        "  Click preview for focus, then press SPACE to arm.\n"
        "  (Classifications before SPACE are ignored — no beep/clip.)",
        flush=True,
    )
    while True:
        if session.arm_event.wait(timeout=0.25):
            return
        with session.lock:
            if session.fatal or session.stop_requested:
                raise RuntimeError("stopped while waiting to arm")


def _operator_thread(
    *,
    session: _Session,
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

            print("\n" + "=" * 60, flush=True)
            print(f"Phase: {scenario.label}", flush=True)
            print(
                f"  Intended maneuver: {scenario.event_type_name}",
                flush=True,
            )
            _wait_for_space(session=session)

            with session.lock:
                session.phase = "armed"
            print(
                f"  Armed — perform {scenario.event_type_name}. "
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
                    f"{scenario.label}: no classification within {ENCOUNTER_TIMEOUT_S:g}s"
                )

            assert observed is not None
            print(
                f"  Classified: {observed.type_name} "
                f"(intended {scenario.event_type_name})",
                flush=True,
            )
            if observed.type_name != scenario.event_type_name:
                raise RuntimeError(
                    f"{scenario.label}: classified {observed.type_name!r} "
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
                    # Never reuse a prior phase's MP4 (that false-passed run-through
                    # when session.clip_path still pointed at clip_1).
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
                        f"{clips_dir} (got no new file after evaluate)"
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
                # Drop any leftover path from a prior finish so waiting_clip
                # cannot accept the previous encounter's MP4.
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
    from db.database import DatabaseUrlError, load_database_url, resolve_sqlite_url
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.backend_auth import apply_edge_env, clear_ingest_auth
    from netrapi.exceptions import NetraPiError

    from _render import api_origin, init_sqlite, sqlite_url, wait_health

    config_dir = DEFAULT_CONFIG_DIR.resolve()
    sqlite_path = SQLITE_PATH

    try:
        apply_edge_env()
        clear_ingest_auth()
        origin = api_origin()
        print("AT-7.3: In-car E2E → deployed cloud", flush=True)
        print(f"  origin: {origin}", flush=True)
        wait_health(origin)

        # Production Pi DB (not wiped). Ensure Alembic head like edge bring-up.
        try:
            db_url = load_database_url(from_process_env=True)
        except DatabaseUrlError:
            db_url = sqlite_url(SQLITE_PATH)
        db_url = resolve_sqlite_url(db_url)
        init_sqlite(db_url)
        if db_url.startswith("sqlite:///"):
            sqlite_path = Path(db_url[len("sqlite:///") :])

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

    print("  camera + EventManager: live (no stubs)")
    print("  persist + ingest: RecordingManager / LocalStore / CloudIngest")
    print(f"  sqlite: {sqlite_path}")
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
        "SPACE to arm each phase"
    )
    print("\nCtrl+C aborts. Camera + Coral + buzzer required.")
    print(
        "Drive each phase after SPACE: complete stop, then rolling, then run-through."
    )

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
        _install_probes(manager, session=session, probe=probe)
        _install_preview_helpers(manager, session=session)

        worker = threading.Thread(
            target=_operator_thread,
            name="at73-operator",
            kwargs={
                "session": session,
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
                print(
                    f"  sqlite/postgres {type_value} event {event_id} -> metadata only"
                )
            else:
                print(f"  sqlite/postgres {type_value} event {event_id} -> {s3_key}")
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
            f"  [{item.scenario.event_type_name}] classified={item.classified_as}  "
            f"latency={latency}  clip={clip}"
        )
    print("\nAT-7.3: PASS")
    print(f"  inspect sqlite: {sqlite_path}")
    print("  inspect Postgres/S3/Render: see README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
