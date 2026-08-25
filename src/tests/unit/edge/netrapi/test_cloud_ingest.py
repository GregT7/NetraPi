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
    clip_dir = tmp_path / "clip_1"
    clip_dir.mkdir()
    clip_path = clip_dir / "clip.mp4"
    clip_path.write_bytes(b"fake-mp4")
    (clip_dir / "areas.json").write_text("{}", encoding="utf-8")
    (clip_dir / "motion.json").write_text("{}", encoding="utf-8")
    (clip_dir / "transitions.json").write_text("{}", encoding="utf-8")
    started = datetime(2026, 8, 16, 18, 0, 0)
    calls: list[tuple] = []

    def json_request(method: str, path: str, body):
        calls.append((method, path, body))
        if path.endswith("s3-upload-url"):
            return {
                "url": "https://s3.example/put-video",
                "object_key": "Aug-2026/driving_session_id_1/clips/clip-1/clip.mp4",
                "method": "PUT",
                "objects": [
                    {
                        "name": "clip.mp4",
                        "url": "https://s3.example/put-video",
                        "object_key": "Aug-2026/driving_session_id_1/clips/clip-1/clip.mp4",
                        "content_type": "video/mp4",
                    },
                    {
                        "name": "areas.json",
                        "url": "https://s3.example/put-areas",
                        "object_key": "Aug-2026/driving_session_id_1/clips/clip-1/areas.json",
                        "content_type": "application/json",
                    },
                    {
                        "name": "motion.json",
                        "url": "https://s3.example/put-motion",
                        "object_key": "Aug-2026/driving_session_id_1/clips/clip-1/motion.json",
                        "content_type": "application/json",
                    },
                    {
                        "name": "transitions.json",
                        "url": "https://s3.example/put-transitions",
                        "object_key": "Aug-2026/driving_session_id_1/clips/clip-1/transitions.json",
                        "content_type": "application/json",
                    },
                ],
            }
        return {"ok": True}

    put_calls: list[tuple] = []

    def put_file(put_url: str, path: Path, content_type: str) -> None:
        put_calls.append((put_url, path.read_bytes(), content_type))

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

    CloudIngest(json_request=json_request, put_file=put_file).sync_session(session_id)
    CloudIngest(json_request=json_request, put_file=put_file).sync_event(event_id)

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
    assert put_calls == [
        ("https://s3.example/put-video", b"fake-mp4", "video/mp4"),
        ("https://s3.example/put-areas", b"{}", "application/json"),
        ("https://s3.example/put-motion", b"{}", "application/json"),
        ("https://s3.example/put-transitions", b"{}", "application/json"),
    ]
    with get_session() as session:
        clip = session.exec(select(Clip).where(Clip.event_id == event_id)).first()
        assert clip is not None
        assert clip.s3_key == "Aug-2026/driving_session_id_1/clips/clip-1/clip.mp4"
        assert clip.s3_stored is True
        assert clip.file_size_bytes == len(b"fake-mp4")


def test_put_clip_objects_logs_json_sidecars_once(tmp_path: Path) -> None:
    clip_dir = tmp_path / "clip_1"
    clip_dir.mkdir()
    clip_path = clip_dir / "clip.mp4"
    clip_path.write_bytes(b"mp4")
    (clip_dir / "areas.json").write_text("{}", encoding="utf-8")
    (clip_dir / "motion.json").write_text("{}", encoding="utf-8")
    (clip_dir / "transitions.json").write_text("{}", encoding="utf-8")
    messages: list[str] = []
    put_names: list[str] = []

    def put_file(_url: str, path: Path, _content_type: str) -> None:
        put_names.append(path.name)

    key = CloudIngest(
        json_request=lambda *_: {},
        put_file=put_file,
        on_log=messages.append,
    )._put_clip_objects(
        {
            "object_key": "Aug-2026/driving_session_id_1/clips/clip-1/clip.mp4",
            "objects": [
                {
                    "name": "clip.mp4",
                    "url": "https://s3.example/put-video",
                    "content_type": "video/mp4",
                },
                {
                    "name": "areas.json",
                    "url": "https://s3.example/put-areas",
                    "content_type": "application/json",
                },
                {
                    "name": "motion.json",
                    "url": "https://s3.example/put-motion",
                    "content_type": "application/json",
                },
                {
                    "name": "transitions.json",
                    "url": "https://s3.example/put-transitions",
                    "content_type": "application/json",
                },
            ],
        },
        clip_path,
    )
    assert key.endswith("clip.mp4")
    assert put_names == ["clip.mp4", "areas.json", "motion.json", "transitions.json"]
    assert messages == [
        "[ingest] uploading json: areas.json, motion.json, transitions.json",
        "[ingest] json uploaded",
    ]
    assert not any("PUT start" in message or "PUT progress" in message for message in messages)


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

    def put_file(*_args):
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
        clip.s3_key = "Aug-2026/driving_session_id_1/clips/clip-1.mp4"
        clip.s3_stored = True
        session.add(clip)
        session.commit()

    CloudIngest(json_request=json_request, put_file=put_file).sync_event(event_id)
    assert "/api/netrapi/driving-event" in calls
    assert "/api/netrapi/s3-upload-url" not in calls
    assert "/api/netrapi/confirm-s3-upload" not in calls


def test_sync_event_metadata_only_skips_s3(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    started = datetime(2026, 8, 16, 18, 0, 0)
    calls: list[tuple[str, str, object]] = []

    def json_request(method: str, path: str, body):
        calls.append((method, path, body))
        return {"ok": True}

    def put_file(*_args):
        raise AssertionError("metadata-only event must not PUT to S3")

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=12),
            type_value="complete-stop",
        )
        session.commit()
        event_id = event.id

    CloudIngest(json_request=json_request, put_file=put_file).sync_event(event_id)
    paths = [item[1] for item in calls]
    assert "/api/netrapi/driving-event" in paths
    assert "/api/netrapi/s3-upload-url" not in paths
    event_body = next(
        item[2] for item in calls if item[1] == "/api/netrapi/driving-event"
    )
    assert "clip" not in event_body


def test_sync_trip_segment_does_not_put(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    started = datetime(2026, 8, 16, 18, 0, 0)
    calls: list[str] = []

    def json_request(method: str, path: str, body):
        calls.append(path)
        return {}

    def put_file(*_args):
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

    CloudIngest(json_request=json_request, put_file=put_file).sync_trip_segment(
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
                "object_key": "Aug-2026/driving_session_id_1/trips/trip-1.mp4",
                "method": "PUT",
            }
        return {"ok": True}

    put_calls: list[tuple] = []

    def put_file(put_url: str, path: Path, content_type: str) -> None:
        put_calls.append((put_url, path.read_bytes(), content_type))

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
        json_request=json_request, put_file=put_file
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
        assert row.s3_key == "Aug-2026/driving_session_id_1/trips/trip-1.mp4"
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

    def put_file(*_args):
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
        stored.s3_key = "Aug-2026/driving_session_id_1/trips/trip-1.mp4"
        stored.s3_stored = True
        session.add(stored)
        session.commit()

    uploaded = CloudIngest(
        json_request=json_request, put_file=put_file
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
                "object_key": (
                    f"Aug-2026/driving_session_id_1/trips/"
                    f"trip-{body['trip_segment_id']}.mp4"
                ),
                "method": "PUT",
            }
        return {"ok": True}

    def put_file(*_args) -> None:
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
        stored_row.s3_key = "Aug-2026/driving_session_id_1/trips/trip-already.mp4"
        stored_row.s3_stored = True
        session.add(stored_row)
        session.commit()

    uploaded = CloudIngest(
        json_request=json_request, put_file=put_file
    ).drain_trip_segments()
    assert uploaded == 1
    assert put_ids == [pending_id]
    with get_session() as session:
        row = session.get(TripSegment, pending_id)
        assert row is not None
        assert row.s3_stored is True
        assert (
            row.s3_key
            == f"Aug-2026/driving_session_id_1/trips/trip-{pending_id}.mp4"
        )


def test_drain_clips_uploads_pending(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"fake-mp4")
    started = datetime(2026, 8, 16, 18, 0, 0)
    put_ids: list[int] = []

    def json_request(method: str, path: str, body):
        if path.endswith("s3-upload-url"):
            put_ids.append(body.get("event_id") or body.get("clip_id"))
            return {
                "url": "https://s3.example/clip-put",
                "object_key": "Aug-2026/driving_session_id_1/clips/clip-pending.mp4",
                "method": "PUT",
            }
        return {"ok": True}

    def put_file(*_args) -> None:
        return None

    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        pending = insert_local_event(
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
        stored = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=20),
            type_value="complete-stop",
            clip_path=clip_path,
            fps=30,
            order_number=2,
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
        pending_id = pending.id
        stored_id = stored.id
        stored_clip = session.exec(select(Clip).where(Clip.event_id == stored_id)).first()
        assert stored_clip is not None
        stored_clip.s3_key = "Aug-2026/driving_session_id_1/clips/clip-already.mp4"
        stored_clip.s3_stored = True
        session.add(stored_clip)
        session.commit()

    uploaded = CloudIngest(
        json_request=json_request, put_file=put_file
    ).drain_clips()
    assert uploaded == 1
    with get_session() as session:
        clip = session.exec(select(Clip).where(Clip.event_id == pending_id)).first()
        assert clip is not None
        assert clip.s3_stored is True
        assert clip.s3_key == "Aug-2026/driving_session_id_1/clips/clip-pending.mp4"


def test_sync_session_missing_row_raises(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    _upgrade(url)
    with pytest.raises(CloudIngestError, match="driving_session 99"):
        CloudIngest(json_request=lambda *_: {}, put_file=lambda *_: None).sync_session(
            99
        )


def test_progress_reader_emits_on_chunk_threshold(tmp_path: Path) -> None:
    from netrapi.cloud_ingest import _ProgressReader

    path = tmp_path / "blob.bin"
    path.write_bytes(b"x" * 12_000)
    messages: list[str] = []
    with path.open("rb") as fh:
        reader = _ProgressReader(
            fh,
            size=12_000,
            label="blob.bin",
            on_progress=messages.append,
            log_every_bytes=4_000,
            log_every_s=9999.0,
        )
        while True:
            chunk = reader.read(3_000)
            if not chunk:
                break
    assert any("PUT progress blob.bin" in message for message in messages)
    assert any("(100%)" in message for message in messages)


def test_http_put_file_streams_and_logs(tmp_path: Path) -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from netrapi.cloud_ingest import PUT_TIMEOUT_S, _http_put_file

    assert PUT_TIMEOUT_S == 1200.0

    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_PUT(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            received["body"] = body
            received["content_type"] = self.headers.get("Content-Type")
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        path = tmp_path / "stream.mp4"
        payload = b"streamed-video-bytes-0123456789"
        path.write_bytes(payload)
        messages: list[str] = []
        port = server.server_address[1]
        _http_put_file(
            f"http://127.0.0.1:{port}/object",
            path,
            "video/mp4",
            on_progress=messages.append,
            timeout_s=30.0,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5.0)

    assert received.get("body") == payload
    assert received.get("content_type") == "video/mp4"
    assert any("PUT start stream.mp4" in message for message in messages)
    assert any("PUT done stream.mp4" in message for message in messages)
    assert any("streaming" in message for message in messages)
