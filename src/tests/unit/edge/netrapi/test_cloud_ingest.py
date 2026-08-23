from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sqlmodel import select

from db.database import get_session, init_engine, set_database_url_override
from db.models import Clip, TripSegment
from db.writes import insert_driving_session, insert_local_event, insert_trip_segment
from netrapi.backend_auth import clear_ingest_auth
from netrapi.cloud_ingest import CloudIngest, try_cloud_ingest, _iso
from netrapi.exceptions import CloudIngestError

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


def test_iso_naive_appends_z() -> None:
    assert _iso(datetime(2026, 8, 16, 18, 0, 0)) == "2026-08-16T18:00:00Z"


def test_sync_master_config_posts_snapshot_payload(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    calls: list[tuple] = []

    def json_request(method: str, path: str, body):
        calls.append((method, path, body))
        return {"id": 1, "created": False}

    CloudIngest(json_request=json_request).sync_master_config(1)

    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/netrapi/master-config"
    assert calls[0][2]["id"] == 1
    assert calls[0][2]["camera"]["selected_mode_key"] == "mjpeg_640x480_30"
    assert calls[0][2]["knn"]["features"][0]["feature_name"] == "post_drop_mean_motion"



def test_try_cloud_ingest_returns_none_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_ingest_auth()
    monkeypatch.delenv("NETRAPI_API_URL", raising=False)
    monkeypatch.delenv("NETRAPI_API_KEY", raising=False)
    assert try_cloud_ingest() is None


def test_try_cloud_ingest_returns_client(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_ingest_auth()
    monkeypatch.setenv("NETRAPI_API_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("NETRAPI_API_KEY", "k")
    client = try_cloud_ingest()
    assert isinstance(client, CloudIngest)
    clear_ingest_auth()


def test_sync_session_and_event_then_clip_put(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"fake-mp4")
    started = datetime(2026, 8, 16, 18, 0, 0)
    calls: list[tuple] = []

    def json_request(method: str, path: str, body):
        calls.append((method, path, body))
        if path.endswith("s3-upload-url"):
            return {
                "url": "https://s3.example/put",
                "object_key": "device-1/2026-08-16/clip-1.mp4",
                "method": "PUT",
            }
        return {"ok": True}

    put_calls: list[tuple] = []

    def put_bytes(put_url: str, payload: bytes, content_type: str) -> None:
        put_calls.append((put_url, payload, content_type))

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=12),
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
                "fail_reasons": (),
            },
        )
        session.commit()
        event_id = event.id
        session_id = driving.id

    CloudIngest(json_request=json_request, put_bytes=put_bytes).sync_session(session_id)
    CloudIngest(json_request=json_request, put_bytes=put_bytes).sync_event(event_id)

    paths = [item[1] for item in calls]
    assert "/api/netrapi/master-config" in paths
    assert "/api/netrapi/driving-session" in paths
    assert "/api/netrapi/driving-event" in paths
    assert "/api/netrapi/s3-upload-url" in paths
    assert "/api/netrapi/confirm-s3-upload" in paths
    event_body = next(
        item[2] for item in calls if item[1] == "/api/netrapi/driving-event"
    )
    assert len(event_body["knn_parameters"]) == 6
    assert event_body["approach_parameters"]["peak_area_pct"] == 1.1
    assert put_calls == [("https://s3.example/put", b"fake-mp4", "video/mp4")]
    with get_session() as session:
        clip = session.exec(select(Clip).where(Clip.event_id == event_id)).first()
        assert clip is not None
        assert clip.s3_key == "device-1/2026-08-16/clip-1.mp4"
        assert clip.s3_stored is True
        assert clip.file_size_bytes == len(b"fake-mp4")


def test_sync_event_skips_put_when_already_stored(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"fake-mp4")
    started = datetime(2026, 8, 16, 18, 0, 0)
    calls: list[str] = []

    def json_request(method: str, path: str, body):
        calls.append(path)
        return {"ok": True}

    def put_bytes(*_args):
        raise AssertionError("already-stored clip must not PUT to S3")

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=12),
            type_value="rolling-stop",
            clip_path=clip_path,
            fps=30,
            order_number=1,
            num_frames=60,
            clip_start=started,
            clip_end=started + timedelta(seconds=2),
        )
        session.commit()
        event_id = event.id
        clip = session.exec(select(Clip).where(Clip.event_id == event_id)).first()
        assert clip is not None
        clip.s3_key = "device-1/2026-08-16/clip-1.mp4"
        clip.s3_stored = True
        session.add(clip)
        session.commit()

    CloudIngest(json_request=json_request, put_bytes=put_bytes).sync_event(event_id)
    assert "/api/netrapi/driving-event" in calls
    assert "/api/netrapi/s3-upload-url" not in calls
    assert "/api/netrapi/confirm-s3-upload" not in calls


def test_sync_trip_segment_does_not_put(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    started = datetime(2026, 8, 16, 18, 0, 0)
    calls: list[str] = []

    def json_request(method: str, path: str, body):
        calls.append(path)
        return {}

    def put_bytes(*_args):
        raise AssertionError("trip segment must not PUT to S3 during ingest")

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        row = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=tmp_path / "seg.mp4",
            start_time=started,
            end_time=started + timedelta(seconds=5),
            order_number=1,
        )
        session.commit()
        segment_id = row.id

    CloudIngest(json_request=json_request, put_bytes=put_bytes).sync_trip_segment(
        segment_id
    )
    assert calls == ["/api/netrapi/trip-segment"]


def test_upload_trip_segment_puts_and_marks_local(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    trip_path = tmp_path / "seg.mp4"
    trip_path.write_bytes(b"fake-trip")
    started = datetime(2026, 8, 16, 18, 0, 0)
    calls: list[tuple] = []

    def json_request(method: str, path: str, body):
        calls.append((method, path, body))
        if path.endswith("s3-upload-url"):
            assert body["trip_segment_id"]
            return {
                "url": "https://s3.example/trip-put",
                "object_key": "device-1/2026-08-16/trip-1.mp4",
                "method": "PUT",
            }
        return {"ok": True}

    put_calls: list[tuple] = []

    def put_bytes(put_url: str, payload: bytes, content_type: str) -> None:
        put_calls.append((put_url, payload, content_type))

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        row = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=trip_path,
            start_time=started,
            end_time=started + timedelta(seconds=5),
            order_number=1,
        )
        session.commit()
        segment_id = row.id

    uploaded = CloudIngest(
        json_request=json_request, put_bytes=put_bytes
    ).upload_trip_segment(segment_id)
    assert uploaded is True
    paths = [item[1] for item in calls]
    assert "/api/netrapi/master-config" in paths
    assert "/api/netrapi/driving-session" in paths
    assert "/api/netrapi/trip-segment" in paths
    assert "/api/netrapi/s3-upload-url" in paths
    assert "/api/netrapi/confirm-s3-upload" in paths
    confirm = next(
        item[2] for item in calls if item[1] == "/api/netrapi/confirm-s3-upload"
    )
    assert confirm["trip_segment_id"] == segment_id
    assert put_calls == [("https://s3.example/trip-put", b"fake-trip", "video/mp4")]
    trip_body = next(
        item[2] for item in calls if item[1] == "/api/netrapi/trip-segment"
    )
    assert trip_body["file_size_bytes"] == len(b"fake-trip")
    with get_session() as session:
        row = session.get(TripSegment, segment_id)
        assert row is not None
        assert row.s3_key == "device-1/2026-08-16/trip-1.mp4"
        assert row.s3_stored is True
        assert row.file_size_bytes == len(b"fake-trip")


def test_upload_trip_segment_skips_put_when_already_stored(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    trip_path = tmp_path / "seg.mp4"
    trip_path.write_bytes(b"fake-trip")
    started = datetime(2026, 8, 16, 18, 0, 0)
    calls: list[str] = []

    def json_request(method: str, path: str, body):
        calls.append(path)
        return {"ok": True}

    def put_bytes(*_args):
        raise AssertionError("already-stored trip must not PUT to S3")

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        row = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=trip_path,
            start_time=started,
            end_time=started + timedelta(seconds=5),
            order_number=1,
        )
        session.commit()
        segment_id = row.id
        stored = session.get(TripSegment, segment_id)
        assert stored is not None
        stored.s3_key = "device-1/2026-08-16/trip-1.mp4"
        stored.s3_stored = True
        session.add(stored)
        session.commit()

    uploaded = CloudIngest(
        json_request=json_request, put_bytes=put_bytes
    ).upload_trip_segment(segment_id)
    assert uploaded is True
    assert "/api/netrapi/trip-segment" in calls
    assert "/api/netrapi/s3-upload-url" not in calls
    assert "/api/netrapi/confirm-s3-upload" not in calls


def test_drain_trip_segments_uploads_finished_pending_only(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    pending_path = tmp_path / "pending.mp4"
    pending_path.write_bytes(b"pending-trip")
    stored_path = tmp_path / "stored.mp4"
    stored_path.write_bytes(b"stored-trip")
    started = datetime(2026, 8, 16, 18, 0, 0)
    put_ids: list[int] = []

    def json_request(method: str, path: str, body):
        if path.endswith("s3-upload-url"):
            put_ids.append(body["trip_segment_id"])
            return {
                "url": "https://s3.example/trip-put",
                "object_key": f"device-1/2026-08-16/trip-{body['trip_segment_id']}.mp4",
                "method": "PUT",
            }
        return {"ok": True}

    def put_bytes(*_args) -> None:
        return None

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        pending = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=pending_path,
            start_time=started,
            end_time=started + timedelta(seconds=5),
            order_number=1,
        )
        stored = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=stored_path,
            start_time=started,
            end_time=started + timedelta(seconds=5),
            order_number=2,
        )
        insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=tmp_path / "open.mp4",
            start_time=started,
            end_time=started,
            order_number=3,
            init_local_stored=None,
        )
        session.commit()
        pending_id = pending.id
        stored_id = stored.id
        stored_row = session.get(TripSegment, stored_id)
        assert stored_row is not None
        stored_row.s3_key = "device-1/2026-08-16/trip-already.mp4"
        stored_row.s3_stored = True
        session.add(stored_row)
        session.commit()

    uploaded = CloudIngest(
        json_request=json_request, put_bytes=put_bytes
    ).drain_trip_segments()
    assert uploaded == 1
    assert put_ids == [pending_id]
    with get_session() as session:
        row = session.get(TripSegment, pending_id)
        assert row is not None
        assert row.s3_stored is True
        assert row.s3_key == f"device-1/2026-08-16/trip-{pending_id}.mp4"


def test_sync_session_missing_row_raises(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    with pytest.raises(CloudIngestError, match="driving_session 99"):
        CloudIngest(json_request=lambda *_: {}, put_bytes=lambda *_: None).sync_session(
            99
        )
