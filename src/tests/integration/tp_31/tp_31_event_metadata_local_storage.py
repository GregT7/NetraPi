"""
TP-31: Event metadata local storage verification (integration).

Runs the real recording pipeline with a stubbed unsafe stop-sign event
(``ROLLING_STOP``), writes an MP4 clip to the configured clips directory
(``src/main/data/clips``), persists the event graph to an isolated SQLite
file next to this harness, then queries the most recent event row.

Pass criteria (test.md):
- Event row exists in SQLite.
- Row contains valid timestamp, event type, and clip identifier or path.
- Row contains stop-sign-related metadata such as stop duration, minimum
  motion, and detection confidence.

Classification is stubbed (same pattern as TP-26 / TP-27). kNN / approach
values are the representative feature set the live EventManager computes;
detector box score is not a schema column, so approach ``log_linear_r2`` is
the stored confidence-like metric.

Usage (from repo root, Pi edge venv with Coral + ffmpeg + buzzer on BCM 18):

    python src/tests/integration/tp_31/tp_31_event_metadata_local_storage.py

No USB camera required (camera is mocked). Coral is required at build time:
``build_pipeline`` always calls ``Detector.load()``. GPIO notify pipes
(``.lgd-nfy*``) that lgpio drops in the working directory are removed on exit.
"""

from __future__ import annotations

import math
import os
import sys
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
MAIN_DIR = SCRIPT_DIR.parents[2] / "main"
EDGE_DIR = MAIN_DIR / "edge"
DB_DIR = MAIN_DIR / "db"
ALEMBIC_INI = DB_DIR / "alembic.ini"
OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"

PRE_ROLL_SECONDS = 2.0
POST_ROLL_SECONDS = 2.0
PRE_FILL_LAP_BUDGET = 150
VERIFY_TPU = False
PREVIEW_ENABLED = False
FULL_RECORD = False
SEEDED_MASTER_CONFIG_ID = 1
UNSAFE_TYPES = frozenset({"rolling-stop", "run-through"})


@dataclass(frozen=True)
class StubMetadata:
    """Stop-sign features stored beside the stubbed ROLLING_STOP event."""

    type_value: str
    stage1_type_value: str
    stage2_type_value: str
    post_drop_mean_motion: float
    post_drop_min_motion: float
    post_drop_p95_motion: float
    post_drop_stop_fraction: float
    approach_area_sum_pct: float
    approach_duration_s: float
    drop_duration_s: float
    peak_area_pct: float
    increasing_fraction: float
    log_linear_r2: float
    post_drop_holds: bool


# Representative rolling-stop feature set (unsafe: did not fully stop).
STUB_METADATA = StubMetadata(
    type_value="rolling-stop",
    stage1_type_value="rolling-or-run-through",
    stage2_type_value="rolling-stop",
    post_drop_mean_motion=0.40,
    post_drop_min_motion=0.12,
    post_drop_p95_motion=0.90,
    post_drop_stop_fraction=0.08,
    approach_area_sum_pct=4.2,
    approach_duration_s=1.8,
    drop_duration_s=0.40,
    peak_area_pct=1.1,
    increasing_fraction=0.70,
    log_linear_r2=0.85,
    post_drop_holds=False,
)


class _FakeCamera:
    """Synthetic frames paced at capture_fps so pre-roll timestamps can fill."""

    def __init__(self, frame: np.ndarray, *, capture_fps: float = 30.0) -> None:
        self._frame = frame
        self.capture_fps = capture_fps
        self._period = 1.0 / capture_fps if capture_fps > 0 else 0.0

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def read(self) -> np.ndarray:
        if self._period > 0:
            time.sleep(self._period)
        return self._frame.copy()

    def measure_fps(self, *, apply: bool = False) -> float:
        if apply:
            self.capture_fps = 30.0
            self._period = 1.0 / self.capture_fps
        return self.capture_fps


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
    for path in (MAIN_DIR, EDGE_DIR):
        path_str = str(path)
        if path_str in sys.path:
            sys.path.remove(path_str)
    sys.path.insert(0, str(MAIN_DIR))
    sys.path.insert(0, str(EDGE_DIR))


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _init_schema(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")

    os.environ["DATABASE_URL"] = url
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")


def _remove_lgpio_notify_pipes(*directories: Path) -> None:
    """lgpio creates ``.lgd-nfy*`` FIFOs in CWD when GPIO opens; unlink leftovers."""
    seen: set[Path] = set()
    for directory in directories:
        try:
            resolved = directory.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        for path in resolved.glob(".lgd-nfy*"):
            try:
                path.unlink()
            except OSError:
                pass


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


def _post_roll_lap_budget(capture_fps: float) -> int:
    return max(1, math.ceil(POST_ROLL_SECONDS * capture_fps - 1e-9) + 30)


def _apply_test_config(
    app_config,
    *,
    repo_root: Path,
    resolve_runtime_paths: Callable,
):
    app_config = resolve_runtime_paths(app_config, repo_root)
    recording = app_config.recording_manager
    buzzer = app_config.buzzer
    app_config = replace(
        app_config,
        recording_manager=replace(
            recording,
            pre_roll_seconds=PRE_ROLL_SECONDS,
            post_roll_seconds=POST_ROLL_SECONDS,
            record_safe_events=False,
        ),
        buzzer=replace(
            buzzer,
            play_on=replace(buzzer.play_on, unsafe=True, safe=False),
        ),
    )
    if not PREVIEW_ENABLED:
        app_config = replace(
            app_config,
            preview=replace(app_config.preview, enabled=False),
        )
    return app_config


def _verify_mp4(path: Path) -> tuple[int, float]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open MP4: {path}")
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"unable to read first frame from {path}")
        return frame_count, fps
    finally:
        capture.release()


def _run_stubbed_unsafe_clip(
    *,
    base_config,
    repo_root: Path,
    resolve_runtime_paths,
    build_pipeline,
    DrivingEvent,
    StopSignEnum,
) -> tuple[Path, int, float, datetime]:
    app_config = _apply_test_config(
        base_config,
        repo_root=repo_root,
        resolve_runtime_paths=resolve_runtime_paths,
    )
    clips_dir = app_config.recording_manager.clips_dir
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips_before = _clip_files(clips_dir)
    print(f"  clips_dir: {clips_dir}")
    post_lap_budget = _post_roll_lap_budget(float(app_config.camera.recommended_fps))
    max_laps = PRE_FILL_LAP_BUDGET + post_lap_budget + 60

    pipeline = build_pipeline(app_config)
    manager = pipeline.manager

    cam = app_config.camera
    frame = np.zeros((cam.height, cam.width, cam.channels), dtype=np.uint8)
    manager._camera = _FakeCamera(frame, capture_fps=float(cam.recommended_fps))

    stub = _DeferredEventStub()
    manager._event_manager = stub
    event = DrivingEvent(type=StopSignEnum.ROLLING_STOP)

    phase = "prefill"
    idle_laps = 0
    triggered_at: datetime | None = None

    def should_stop() -> bool:
        nonlocal phase, idle_laps, triggered_at
        if _clip_files(clips_dir) - clips_before:
            return True
        if phase == "prefill":
            idle_laps += 1
            if idle_laps > PRE_FILL_LAP_BUDGET:
                return True
            if _pre_roll_window_full(manager.pre_buffer):
                print(
                    f"  Arming ROLLING_STOP after {idle_laps} idle lap(s) "
                    f"(pre_buffer={len(manager.pre_buffer)}, "
                    f"span={_pre_buffer_time_span(manager.pre_buffer):.2f}s) ..."
                )
                stub.arm(event)
                phase = "armed"
            return False
        if phase == "armed":
            if manager.clip_active:
                triggered_at = datetime.now()
                phase = "post"
            return False
        if phase == "post":
            return not manager.clip_active
        return True

    print("  Running stubbed ROLLING_STOP through RecordingManager ...")
    manager.run_loop(
        max_laps=max_laps,
        should_stop=should_stop,
        full_record=FULL_RECORD,
    )

    new_clips = _clip_files(clips_dir) - clips_before
    if not new_clips:
        raise RuntimeError(
            f"no clip written (phase={phase!r}, clip_active={manager.clip_active}, "
            f"idle_laps={idle_laps})"
        )
    if len(new_clips) != 1:
        names = ", ".join(path.name for path in sorted(new_clips))
        raise RuntimeError(f"expected 1 new clip, got {len(new_clips)}: {names}")

    clip_path = next(iter(new_clips))
    frame_count, clip_fps = _verify_mp4(clip_path)
    if frame_count < 2:
        raise RuntimeError(f"clip {clip_path.name} has {frame_count} frames; expected >= 2")
    if triggered_at is None:
        triggered_at = datetime.now()
    print(f"  clip_path: {clip_path}")
    print(f"  clip_frame_count: {frame_count}")
    print(f"  clip_fps: {clip_fps:.2f}")
    return clip_path, frame_count, clip_fps, triggered_at


def _type_ids_by_value(session) -> dict[str, int]:
    from sqlmodel import select

    from db.models import ClassificationType

    rows = session.exec(select(ClassificationType)).all()
    return {row.value: row.id for row in rows if row.id is not None}


def _knn_features_by_stage_name(session) -> dict[tuple[int, str], int]:
    from sqlmodel import select

    from db.models import KnnFeature

    rows = session.exec(select(KnnFeature)).all()
    mapping: dict[tuple[int, str], int] = {}
    for row in rows:
        if row.id is None:
            continue
        mapping[(row.stage, row.feature_name)] = row.id
    return mapping


def _persist_event(
    session,
    *,
    metadata: StubMetadata,
    clip_path: Path,
    frame_count: int,
    clip_fps: float,
    triggered_at: datetime,
) -> int:
    from db.models import (
        ApproachParameters,
        AutoClassification,
        Classification,
        Clip,
        DrivingSession,
        Event,
        KnnParameter,
        MasterConfig,
    )

    master = session.get(MasterConfig, SEEDED_MASTER_CONFIG_ID)
    if master is None:
        raise RuntimeError(
            f"Seeded master_config id={SEEDED_MASTER_CONFIG_ID} missing after Alembic upgrade"
        )

    type_ids = _type_ids_by_value(session)
    required_types = {
        metadata.type_value,
        metadata.stage1_type_value,
        metadata.stage2_type_value,
    }
    missing_types = sorted(required_types - type_ids.keys())
    if missing_types:
        raise RuntimeError(f"classification_type rows missing for {missing_types}")

    knn_ids = _knn_features_by_stage_name(session)
    knn_values = {
        (1, "post_drop_mean_motion"): metadata.post_drop_mean_motion,
        (1, "post_drop_min_motion"): metadata.post_drop_min_motion,
        (1, "post_drop_p95_motion"): metadata.post_drop_p95_motion,
        (1, "post_drop_stop_fraction"): metadata.post_drop_stop_fraction,
        (2, "post_drop_min_motion"): metadata.post_drop_min_motion,
        (2, "approach_area_sum_pct"): metadata.approach_area_sum_pct,
    }
    missing_knn = [key for key in knn_values if key not in knn_ids]
    if missing_knn:
        raise RuntimeError(f"knn_feature rows missing for {missing_knn}")

    fps = max(1, int(round(clip_fps)))
    clip_start = triggered_at - timedelta(seconds=PRE_ROLL_SECONDS)
    clip_end = triggered_at + timedelta(seconds=POST_ROLL_SECONDS)

    driving_session = DrivingSession(
        master_config_id=master.id,
        start_time=clip_start,
        end_time=None,
    )
    session.add(driving_session)
    session.flush()
    if driving_session.id is None:
        raise RuntimeError("driving_session insert did not assign an id")

    event = Event(driving_session_id=driving_session.id, time=triggered_at)
    session.add(event)
    session.flush()
    if event.id is None:
        raise RuntimeError("event insert did not assign an id")

    classification = Classification(
        event_id=event.id,
        classification_type_id=type_ids[metadata.type_value],
        kind="auto",
    )
    session.add(classification)
    session.flush()
    if classification.id is None:
        raise RuntimeError("classification insert did not assign an id")

    auto = AutoClassification(
        classification_id=classification.id,
        stage1_classification_type_id=type_ids[metadata.stage1_type_value],
        stage2_classification_type_id=type_ids[metadata.stage2_type_value],
    )
    session.add(auto)
    session.flush()
    if auto.id is None:
        raise RuntimeError("auto_classification insert did not assign an id")

    session.add(
        ApproachParameters(
            auto_classification_id=auto.id,
            peak_area_pct=metadata.peak_area_pct,
            approach_duration_s=metadata.approach_duration_s,
            increasing_fraction=metadata.increasing_fraction,
            log_linear_r2=metadata.log_linear_r2,
            drop_duration_s=metadata.drop_duration_s,
            post_drop_holds=metadata.post_drop_holds,
        )
    )
    for key, value in knn_values.items():
        session.add(
            KnnParameter(
                auto_classification_id=auto.id,
                knn_feature_id=knn_ids[key],
                value=value,
            )
        )
    session.add(
        Clip(
            event_id=event.id,
            local_path=str(clip_path),
            init_local_stored=True,
            fps=fps,
            order_number=1,
            num_frames=frame_count,
            start_time=clip_start,
            end_time=clip_end,
        )
    )
    session.commit()
    print(
        f"  persisted event id={event.id} time={triggered_at.isoformat()} "
        f"type={metadata.type_value} clip={clip_path}"
    )
    return event.id


def _inspect_latest_event(session, *, expected_clip: Path, metadata: StubMetadata) -> None:
    from sqlmodel import select

    from db.models import (
        ApproachParameters,
        AutoClassification,
        Classification,
        ClassificationType,
        Clip,
        Event,
        KnnFeature,
        KnnParameter,
    )

    event = session.exec(select(Event).order_by(Event.id.desc())).first()
    if event is None:
        raise AssertionError("no event row in SQLite")
    if event.time is None:
        raise AssertionError("event.time is missing")

    classification = session.exec(
        select(Classification).where(Classification.event_id == event.id)
    ).one()
    type_row = session.get(ClassificationType, classification.classification_type_id)
    if type_row is None:
        raise AssertionError("classification_type row missing")
    if type_row.value not in UNSAFE_TYPES:
        raise AssertionError(
            f"event type {type_row.value!r} is not an unsafe stop-sign class "
            f"{sorted(UNSAFE_TYPES)}"
        )
    if type_row.value != metadata.type_value:
        raise AssertionError(
            f"event type {type_row.value!r} != stub {metadata.type_value!r}"
        )

    clip = session.exec(select(Clip).where(Clip.event_id == event.id)).one()
    if not clip.local_path:
        raise AssertionError("clip.local_path is missing")
    if Path(clip.local_path).resolve() != expected_clip.resolve():
        raise AssertionError(
            f"clip.local_path {clip.local_path!r} != pipeline clip {expected_clip}"
        )
    if not Path(clip.local_path).is_file():
        raise AssertionError(f"clip file does not exist: {clip.local_path}")

    auto = session.exec(
        select(AutoClassification).where(
            AutoClassification.classification_id == classification.id
        )
    ).one()
    approach = session.exec(
        select(ApproachParameters).where(
            ApproachParameters.auto_classification_id == auto.id
        )
    ).one()
    if approach.approach_duration_s <= 0:
        raise AssertionError(
            f"approach_duration_s (stop duration) must be > 0, "
            f"got {approach.approach_duration_s}"
        )
    if approach.log_linear_r2 < 0:
        raise AssertionError(
            f"log_linear_r2 (confidence-like) must be >= 0, got {approach.log_linear_r2}"
        )

    knn_rows = session.exec(
        select(KnnParameter).where(KnnParameter.auto_classification_id == auto.id)
    ).all()
    knn_by_name: dict[tuple[int, str], float] = {}
    for param in knn_rows:
        feature = session.get(KnnFeature, param.knn_feature_id)
        if feature is None:
            raise AssertionError(f"knn_feature id={param.knn_feature_id} missing")
        knn_by_name[(feature.stage, feature.feature_name)] = param.value
    min_motion = knn_by_name.get((1, "post_drop_min_motion"))
    if min_motion is None:
        raise AssertionError("knn_parameter post_drop_min_motion (stage 1) missing")
    if min_motion < 0:
        raise AssertionError(f"post_drop_min_motion must be >= 0, got {min_motion}")

    print(f"  latest event id={event.id}")
    print(f"  timestamp: {event.time.isoformat()}")
    print(f"  event type: {type_row.value} (kind={classification.kind})")
    print(f"  clip path: {clip.local_path}")
    print(f"  stop duration (approach_duration_s): {approach.approach_duration_s}")
    print(f"  minimum motion (post_drop_min_motion): {min_motion}")
    print(f"  detection confidence (log_linear_r2): {approach.log_linear_r2}")


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.events import DrivingEvent, StopSignEnum
    from netrapi.exceptions import NetraPiError

    import db.database as database
    from db.database import get_session, init_engine

    config_dir = DEFAULT_CONFIG_DIR.resolve()
    print("TP-31: Event metadata local storage verification", flush=True)
    print("  1. Initialize SQLite (Alembic upgrade head)", flush=True)
    print("  2. Trigger stubbed ROLLING_STOP and write a clip", flush=True)
    print("  3. Persist event + clip + stop-sign metadata", flush=True)
    print("  4. Query the most recent SQLite event row", flush=True)

    previous_url = os.environ.get("DATABASE_URL")
    try:
        base_config = AppConfig.load(config_dir)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    try:
        if OUTPUT_DB_PATH.exists():
            OUTPUT_DB_PATH.unlink()
        url = _sqlite_url(OUTPUT_DB_PATH)
        print(f"  sqlite: {OUTPUT_DB_PATH}")
        _init_schema(url)

        clip_path, frame_count, clip_fps, triggered_at = _run_stubbed_unsafe_clip(
            base_config=base_config,
            repo_root=REPO_ROOT,
            resolve_runtime_paths=_resolve_runtime_paths,
            build_pipeline=build_pipeline,
            DrivingEvent=DrivingEvent,
            StopSignEnum=StopSignEnum,
        )

        init_engine(url)
        with get_session() as session:
            _persist_event(
                session,
                metadata=STUB_METADATA,
                clip_path=clip_path,
                frame_count=frame_count,
                clip_fps=clip_fps,
                triggered_at=triggered_at,
            )

        if database._engine is not None:
            database._engine.dispose()
        database._engine = None

        init_engine(url)
        with get_session() as session:
            _inspect_latest_event(
                session,
                expected_clip=clip_path,
                metadata=STUB_METADATA,
            )

        if database._engine is not None:
            database._engine.dispose()
        database._engine = None
    except NetraPiError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        _remove_lgpio_notify_pipes(SCRIPT_DIR, Path.cwd())
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url

    print("PASS: unsafe event stored in SQLite with timestamp, type, clip path, and metadata")
    print(f"  inspect db: {OUTPUT_DB_PATH}")
    print(f"  inspect clip: {clip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
