from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import select

from db.database import get_session, init_engine
from db.models import (
    ApproachFailReason,
    ApproachParameters,
    AutoClassification,
    Classification,
    ClassificationType,
    Clip,
    DrivingSession,
    Event,
    EventTripLocation,
    KnnParameter,
    TripSegment,
)
from db.writes import (
    COMPLETE_STOP,
    STAGE1_UNSAFE,
    attach_local_clip,
    end_driving_session,
    insert_driving_session,
    insert_local_event,
    insert_trip_segment,
    update_trip_segment,
)

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "main" / "db" / "alembic.ini"


def _upgrade(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    import db.database as database

    database.set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def test_insert_local_event_metadata_only_then_attach_clip(
    sqlite_url: str, tmp_path: Path
) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    started = datetime(2026, 8, 22, 14, 0, 0)
    clip_path = tmp_path / "later.mp4"
    clip_path.write_bytes(b"mp4")
    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started,
            type_value=COMPLETE_STOP,
        )
        session.commit()
        event_id = event.id
    with get_session() as session:
        assert (
            session.exec(select(Clip).where(Clip.event_id == event_id)).first() is None
        )
        clip = attach_local_clip(
            session,
            event_id,
            clip_path=clip_path,
            fps=30,
            order_number=1,
            num_frames=60,
            clip_start=started,
            clip_end=started + timedelta(seconds=2),
        )
        session.commit()
        clip_id = clip.id
    with get_session() as session:
        row = session.get(Clip, clip_id)
        assert row is not None
        assert row.event_id == event_id
        assert row.local_path == str(clip_path)
        assert row.init_local_stored is True
        assert row.file_size_bytes == 3


def test_insert_local_event_complete_stop(sqlite_url: str, tmp_path: Path) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    started = datetime(2026, 8, 22, 12, 0, 0)
    clip_start = started
    clip_end = started + timedelta(seconds=10)
    clip_path = tmp_path / "complete.mp4"
    clip_path.write_bytes(b"abc")
    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=5),
            type_value=COMPLETE_STOP,
            clip_path=clip_path,
            fps=30,
            order_number=1,
            num_frames=300,
            clip_start=clip_start,
            clip_end=clip_end,
        )
        session.commit()
        event_id = event.id
    with get_session() as session:
        classification = session.exec(
            select(Classification).where(Classification.event_id == event_id)
        ).one()
        type_row = session.get(ClassificationType, classification.classification_type_id)
        auto = session.exec(
            select(AutoClassification).where(
                AutoClassification.classification_id == classification.id
            )
        ).one()
        clip = session.exec(select(Clip).where(Clip.event_id == event_id)).one()
        assert type_row is not None
        assert type_row.value == COMPLETE_STOP
        assert auto.stage1_classification_type_id == type_row.id
        assert auto.stage2_classification_type_id is None
        assert clip.s3_key is None
        assert clip.s3_stored is None
        assert clip.init_local_stored is True
        assert clip.file_size_bytes == 3


def test_insert_local_event_rolling_stop_stage2(sqlite_url: str) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    started = datetime(2026, 8, 22, 13, 0, 0)
    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started,
            type_value="rolling-stop",
            clip_path="/tmp/rolling.mp4",
            fps=30,
            order_number=1,
            num_frames=180,
            clip_start=started,
            clip_end=started + timedelta(seconds=6),
        )
        session.commit()
        event_id = event.id
        unsafe_id = session.exec(
            select(ClassificationType).where(ClassificationType.value == STAGE1_UNSAFE)
        ).one().id
        rolling_id = session.exec(
            select(ClassificationType).where(ClassificationType.value == "rolling-stop")
        ).one().id
    with get_session() as session:
        classification = session.exec(
            select(Classification).where(Classification.event_id == event_id)
        ).one()
        auto = session.exec(
            select(AutoClassification).where(
                AutoClassification.classification_id == classification.id
            )
        ).one()
        assert classification.classification_type_id == rolling_id
        assert auto.stage1_classification_type_id == unsafe_id
        assert auto.stage2_classification_type_id == rolling_id


def test_insert_trip_segment_and_end_session(sqlite_url: str) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    started = datetime(2026, 8, 22, 14, 0, 0)
    ended = started + timedelta(seconds=12)
    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        segment = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path="/tmp/trip_seg_0001.mp4",
            start_time=started,
            end_time=ended,
            order_number=1,
        )
        end_driving_session(session, driving.id, end_time=ended)
        session.commit()
        session_id = driving.id
        segment_id = segment.id
    with get_session() as session:
        driving = session.get(DrivingSession, session_id)
        row = session.get(TripSegment, segment_id)
        event_count = len(session.exec(select(Event)).all())
        assert driving is not None
        assert driving.end_time == ended
        assert row is not None
        assert row.s3_stored is None
        assert row.order_number == 1
        assert row.file_size_bytes is None
        assert row.init_local_deleted is None
        assert event_count == 0


def test_finished_trip_segment_records_file_size(
    sqlite_url: str, tmp_path: Path
) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    started = datetime(2026, 8, 22, 14, 30, 0)
    trip_path = tmp_path / "seg.mp4"
    trip_path.write_bytes(b"trip-bytes")
    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        opened = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=trip_path,
            start_time=started,
            end_time=started,
            order_number=1,
            init_local_stored=None,
        )
        session.flush()
        assert opened.id is not None
        assert opened.file_size_bytes is None
        update_trip_segment(
            session,
            opened.id,
            local_path=trip_path,
            end_time=started + timedelta(seconds=5),
            init_local_stored=True,
        )
        session.commit()
        segment_id = opened.id
    with get_session() as session:
        row = session.get(TripSegment, segment_id)
        assert row is not None
        assert row.init_local_stored is True
        assert row.file_size_bytes == len(b"trip-bytes")
        assert row.init_local_deleted is None


def test_insert_local_event_knn_approach_and_trip_location(
    sqlite_url: str, tmp_path: Path
) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    started = datetime(2026, 8, 22, 15, 0, 0)
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"abcd")
    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        segment = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=tmp_path / "seg.mp4",
            start_time=started,
            end_time=started + timedelta(seconds=30),
            order_number=1,
        )
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=5),
            type_value="rolling-stop",
            clip_path=clip_path,
            fps=30,
            order_number=1,
            num_frames=60,
            clip_start=started,
            clip_end=started + timedelta(seconds=2),
            knn_stage1=(0.4, 0.12, 0.9, 0.08),
            knn_stage2=(0.12, 4.2),
            approach={
                "peak_area_pct": 1.1,
                "approach_duration_s": 1.8,
                "increasing_fraction": 0.7,
                "log_linear_r2": 0.85,
                "drop_duration_s": 0.4,
                "post_drop_holds": False,
                "fail_reasons": ("post_drop_hold",),
            },
            trip_segment_id=segment.id,
            trip_offset_seconds=5.0,
        )
        session.commit()
        event_id = event.id

    with get_session() as session:
        knn = session.exec(select(KnnParameter)).all()
        assert len(knn) == 6
        approach = session.exec(select(ApproachParameters)).one()
        assert approach.peak_area_pct == 1.1
        reasons = session.exec(select(ApproachFailReason)).all()
        assert [row.reason for row in reasons] == ["post_drop_hold"]
        loc = session.exec(select(EventTripLocation)).one()
        assert loc.event_id == event_id
        assert loc.trip_offset_seconds == 5.0
