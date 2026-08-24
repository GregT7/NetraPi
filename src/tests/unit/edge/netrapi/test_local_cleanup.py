from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import select

from db.database import get_session, init_engine, set_database_url_override
from db.models import Clip, TripSegment
from db.writes import insert_driving_session, insert_local_event, insert_trip_segment
from netrapi.cloud_ingest import CloudIngest
from netrapi.local_cleanup import delete_all_local_media, delete_uploaded_local_media

ALEMBIC_INI = Path(__file__).resolve().parents[4] / "main" / "db" / "alembic.ini"


@pytest.fixture(autouse=True)
def _reset_engine() -> None:
    yield
    import db.database as database

    set_database_url_override(None)
    if database._engine is not None:
        database._engine.dispose()
        database._engine = None


def _upgrade(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    init_engine(url)


def _ingest() -> tuple[CloudIngest, list[tuple]]:
    calls: list[tuple] = []

    def json_request(method: str, path: str, body):
        calls.append((method, path, body))
        return {"ok": True}

    return CloudIngest(json_request=json_request, put_bytes=lambda *_: None), calls


def test_delete_uploaded_local_only_removes_s3_rows(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    uploaded = tmp_path / "uploaded.mp4"
    pending = tmp_path / "pending.mp4"
    uploaded.write_bytes(b"up")
    pending.write_bytes(b"pend")
    started = datetime(2026, 8, 16, 18, 0, 0)
    ingest, calls = _ingest()

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=1),
            type_value="rolling-stop",
            clip_path=uploaded,
            fps=30,
            order_number=1,
            num_frames=30,
            clip_start=started,
            clip_end=started + timedelta(seconds=1),
        )
        session.commit()
        clip = session.exec(select(Clip).where(Clip.event_id == event.id)).first()
        assert clip is not None
        clip.s3_key = "Aug-2026/driving_session_id_1/clips/clip-1.mp4"
        clip.s3_stored = True
        session.add(clip)
        insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=pending,
            start_time=started,
            end_time=started + timedelta(seconds=5),
            order_number=1,
        )
        session.commit()
        clip_id = clip.id

    cleaned = delete_uploaded_local_media(ingest)
    assert cleaned == 1
    assert not uploaded.is_file()
    assert pending.is_file()
    with get_session() as session:
        row = session.get(Clip, clip_id)
        assert row is not None
        assert row.init_local_deleted is True
        assert row.local_path is None
    assert any(item[1].endswith("confirm-local-delete") for item in calls)


def test_delete_uploaded_local_target_clips_skips_trips(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    clip_file = tmp_path / "clip.mp4"
    trip_file = tmp_path / "trip.mp4"
    clip_file.write_bytes(b"clip")
    trip_file.write_bytes(b"trip")
    started = datetime(2026, 8, 16, 18, 0, 0)
    ingest, calls = _ingest()

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=1),
            type_value="rolling-stop",
            clip_path=clip_file,
            fps=30,
            order_number=1,
            num_frames=30,
            clip_start=started,
            clip_end=started + timedelta(seconds=1),
        )
        session.commit()
        clip = session.exec(select(Clip).where(Clip.event_id == event.id)).first()
        assert clip is not None
        clip.s3_key = "Aug-2026/driving_session_id_1/clips/clip-1.mp4"
        clip.s3_stored = True
        session.add(clip)
        trip = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=trip_file,
            start_time=started,
            end_time=started + timedelta(seconds=5),
            order_number=1,
        )
        trip.s3_key = "Aug-2026/driving_session_id_1/trips/trip-1.mp4"
        trip.s3_stored = True
        session.add(trip)
        session.commit()
        clip_id = clip.id
        trip_id = trip.id

    cleaned = delete_uploaded_local_media(ingest, target="clips")
    assert cleaned == 1
    assert not clip_file.is_file()
    assert trip_file.is_file()
    with get_session() as session:
        clip_row = session.get(Clip, clip_id)
        trip_row = session.get(TripSegment, trip_id)
        assert clip_row is not None
        assert clip_row.init_local_deleted is True
        assert clip_row.local_path is None
        assert trip_row is not None
        assert trip_row.init_local_deleted is not True
        assert trip_row.local_path == str(trip_file)
    assert any(item[1].endswith("confirm-local-delete") for item in calls)


def test_delete_all_local_removes_pending_and_orphans(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    clips_dir = tmp_path / "clips"
    trips_dir = tmp_path / "trips"
    clips_dir.mkdir()
    trips_dir.mkdir()
    pending = clips_dir / "pending.mp4"
    orphan = trips_dir / "orphan.mp4"
    pending.write_bytes(b"pend")
    orphan.write_bytes(b"orph")
    started = datetime(2026, 8, 16, 18, 0, 0)
    ingest, calls = _ingest()

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=1),
            type_value="rolling-stop",
            clip_path=pending,
            fps=30,
            order_number=1,
            num_frames=30,
            clip_start=started,
            clip_end=started + timedelta(seconds=1),
        )
        session.commit()
        clip = session.exec(select(Clip).where(Clip.event_id == event.id)).first()
        assert clip is not None
        clip_id = clip.id

    cleaned = delete_all_local_media(
        ingest, clips_dir=clips_dir, trips_dir=trips_dir
    )
    assert cleaned == 2
    assert not pending.is_file()
    assert not orphan.is_file()
    with get_session() as session:
        row = session.get(Clip, clip_id)
        assert row is not None
        assert row.init_local_deleted is True
        assert row.local_path is None
    bodies = [item[2] for item in calls if item[1].endswith("confirm-local-delete")]
    assert {"clip_id": clip_id} in bodies
