"""
TP-30: Local database write/read smoke test (integration).

Applies Alembic migrations to a temporary SQLite file, inserts dummy event
metadata (session, event, classification, clip), then reads the rows back in a
new session after disposing the engine.

Usage (from repo root, venv with sqlmodel + alembic):

    python src/tests/integration/tp_30/tp_30_local_database_write_read_smoke.py

Leaves `src/tests/integration/tp_30/netrapi.db` for inspection (recreated each run, not deleted after PASS).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
MAIN_DIR = SCRIPT_DIR.parents[2] / "main"
DB_DIR = MAIN_DIR / "db"
ALEMBIC_INI = DB_DIR / "alembic.ini"
OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"

SEEDED_MASTER_CONFIG_ID = 1


@dataclass(frozen=True)
class DummyEventSpec:
    time: datetime
    type_value: str
    clip_local_path: str
    fps: int
    order_number: int
    num_frames: int
    clip_start: datetime
    clip_end: datetime
    kind: str = "auto"


DUMMY_EVENTS: tuple[DummyEventSpec, ...] = (
    DummyEventSpec(
        time=datetime(2026, 8, 15, 11, 15, 0),
        type_value="complete-stop",
        clip_local_path="/tmp/netrapi/clips/dummy_complete_stop.mp4",
        fps=30,
        order_number=1,
        num_frames=180,
        clip_start=datetime(2026, 8, 15, 11, 14, 50),
        clip_end=datetime(2026, 8, 15, 11, 15, 10),
    ),
    DummyEventSpec(
        time=datetime(2026, 8, 15, 11, 42, 30),
        type_value="rolling-stop",
        clip_local_path="/tmp/netrapi/clips/dummy_rolling_stop.mp4",
        fps=30,
        order_number=2,
        num_frames=210,
        clip_start=datetime(2026, 8, 15, 11, 42, 20),
        clip_end=datetime(2026, 8, 15, 11, 42, 40),
    ),
)


def _configure_import_path() -> None:
    main_str = str(MAIN_DIR)
    if main_str not in sys.path:
        sys.path.insert(0, main_str)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _init_schema(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")

    os.environ["DATABASE_URL"] = url
    from db.database import set_database_url_override

    set_database_url_override(url)
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")


def _type_ids_by_value(session) -> dict[str, int]:
    from sqlmodel import select

    from db.models import ClassificationType

    rows = session.exec(select(ClassificationType)).all()
    return {row.value: row.id for row in rows if row.id is not None}


def _insert_dummy_events(session, specs: tuple[DummyEventSpec, ...]) -> list[int]:
    from db.models import Classification, Clip, DrivingSession, Event, MasterConfig

    master = session.get(MasterConfig, SEEDED_MASTER_CONFIG_ID)
    if master is None:
        raise RuntimeError(
            f"Seeded master_config id={SEEDED_MASTER_CONFIG_ID} missing after Alembic upgrade"
        )

    type_ids = _type_ids_by_value(session)
    missing = sorted({spec.type_value for spec in specs} - type_ids.keys())
    if missing:
        raise RuntimeError(f"classification_type rows missing for {missing}")

    driving_session = DrivingSession(
        master_config_id=master.id,
        start_time=datetime(2026, 8, 15, 11, 0, 0),
        end_time=datetime(2026, 8, 15, 12, 0, 0),
    )
    session.add(driving_session)
    session.flush()
    if driving_session.id is None:
        raise RuntimeError("driving_session insert did not assign an id")

    event_ids: list[int] = []
    for spec in specs:
        event = Event(driving_session_id=driving_session.id, time=spec.time)
        session.add(event)
        session.flush()
        if event.id is None:
            raise RuntimeError("event insert did not assign an id")

        session.add(
            Classification(
                event_id=event.id,
                classification_type_id=type_ids[spec.type_value],
                kind=spec.kind,
            )
        )
        session.add(
            Clip(
                event_id=event.id,
                local_path=spec.clip_local_path,
                init_local_stored=True,
                fps=spec.fps,
                order_number=spec.order_number,
                num_frames=spec.num_frames,
                start_time=spec.clip_start,
                end_time=spec.clip_end,
            )
        )
        event_ids.append(event.id)
        print(
            f"  inserted event id={event.id} time={spec.time.isoformat()} "
            f"type={spec.type_value} clip={spec.clip_local_path}"
        )

    session.commit()
    return event_ids


def _read_dummy_events(session, event_ids: list[int]) -> list[tuple]:
    from sqlmodel import select

    from db.models import Classification, ClassificationType, Clip, Event

    rows = []
    for event_id in event_ids:
        event = session.get(Event, event_id)
        if event is None:
            raise AssertionError(f"event id={event_id} was not found after insert")

        classification = session.exec(
            select(Classification).where(Classification.event_id == event_id)
        ).one()
        type_row = session.get(ClassificationType, classification.classification_type_id)
        if type_row is None:
            raise AssertionError(
                f"classification_type id={classification.classification_type_id} missing"
            )
        clip = session.exec(select(Clip).where(Clip.event_id == event_id)).one()
        rows.append((event, classification, type_row, clip))
    return rows


def _assert_round_trip(
    specs: tuple[DummyEventSpec, ...],
    rows: list[tuple],
) -> None:
    if len(rows) != len(specs):
        raise AssertionError(f"expected {len(specs)} events, read {len(rows)}")

    for spec, (event, classification, type_row, clip) in zip(specs, rows):
        if event.time != spec.time:
            raise AssertionError(f"event.time {event.time!r} != {spec.time!r}")
        if type_row.value != spec.type_value:
            raise AssertionError(
                f"classification type {type_row.value!r} != {spec.type_value!r}"
            )
        if classification.kind != spec.kind:
            raise AssertionError(
                f"classification.kind {classification.kind!r} != {spec.kind!r}"
            )
        if clip.local_path != spec.clip_local_path:
            raise AssertionError(
                f"clip.local_path {clip.local_path!r} != {spec.clip_local_path!r}"
            )
        if clip.fps != spec.fps:
            raise AssertionError(f"clip.fps {clip.fps!r} != {spec.fps!r}")
        if clip.order_number != spec.order_number:
            raise AssertionError(
                f"clip.order_number {clip.order_number!r} != {spec.order_number!r}"
            )
        if clip.num_frames != spec.num_frames:
            raise AssertionError(
                f"clip.num_frames {clip.num_frames!r} != {spec.num_frames!r}"
            )
        if clip.start_time != spec.clip_start:
            raise AssertionError(
                f"clip.start_time {clip.start_time!r} != {spec.clip_start!r}"
            )
        if clip.end_time != spec.clip_end:
            raise AssertionError(
                f"clip.end_time {clip.end_time!r} != {spec.clip_end!r}"
            )
        if clip.init_local_stored is not True:
            raise AssertionError(
                f"clip.init_local_stored {clip.init_local_stored!r} != True"
            )
        print(
            f"  matched event id={event.id} time={event.time.isoformat()} "
            f"type={type_row.value} clip={clip.local_path}"
        )


def run_smoke(db_path: Path) -> None:
    import db.database as database
    from db.database import get_session, init_engine

    url = _sqlite_url(db_path)
    print(f"  sqlite: {db_path}")
    _init_schema(url)

    init_engine(url)
    with get_session() as session:
        event_ids = _insert_dummy_events(session, DUMMY_EVENTS)

    if database._engine is not None:
        database._engine.dispose()
    database._engine = None

    init_engine(url)
    with get_session() as session:
        rows = _read_dummy_events(session, event_ids)
        _assert_round_trip(DUMMY_EVENTS, rows)

    if database._engine is not None:
        database._engine.dispose()
    database._engine = None


def main() -> int:
    _configure_import_path()

    print("TP-30: Local database write/read smoke", flush=True)
    print("  1. Initialize SQLite schema (Alembic upgrade head)", flush=True)
    print("  2. Insert dummy event records", flush=True)
    print("  3. Read them back from a new session", flush=True)

    previous_url = os.environ.get("DATABASE_URL")
    try:
        if OUTPUT_DB_PATH.exists():
            OUTPUT_DB_PATH.unlink()
        run_smoke(OUTPUT_DB_PATH)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url

    print(f"PASS: inserted records round-tripped with matching values")
    print(f"  inspect: {OUTPUT_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
