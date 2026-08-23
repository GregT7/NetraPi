from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.trip_segment import router
from db.database import get_session
from db.models import DrivingSession, TripSegment

_PAYLOAD = {
    "id": 3,
    "driving_session_id": 1,
    "local_path": "/tmp/seg.mp4",
    "init_local_stored": True,
    "start_time": "2026-08-16T18:00:00Z",
    "end_time": "2026-08-16T18:05:00Z",
    "order_number": 3,
}

_HEADERS = {"X-API-Key": "unit-test-netrapi-key"}


def _client() -> TestClient:
    application = FastAPI()
    application.include_router(router)
    return TestClient(application)


def _session_cm(inner: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value = inner
    cm.__exit__.return_value = None
    return cm


def test_unknown_driving_session_returns_400() -> None:
    inner = MagicMock()
    inner.get.return_value = None
    with patch("app.routes.trip_segment.get_session", return_value=_session_cm(inner)):
        response = _client().post(
            "/api/netrapi/trip-segment", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "driving_session 1 not found"


def test_creates_trip_segment_when_row_missing() -> None:
    inner = MagicMock()

    def _get(model, _id):
        if model is DrivingSession:
            return MagicMock()
        return None

    inner.get.side_effect = _get
    with patch("app.routes.trip_segment.get_session", return_value=_session_cm(inner)):
        response = _client().post(
            "/api/netrapi/trip-segment", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 200
    created = inner.add.call_args.args[0]
    assert isinstance(created, TripSegment)
    assert created.id == 3
    assert created.s3_key is None
    assert created.s3_stored is None
    assert created.init_local_deleted is None
    assert created.file_size_bytes is None


def test_upsert_preserves_s3_fields_and_ignores_client_s3(
    ingest_client: TestClient,
) -> None:
    session = ingest_client.post(
        "/api/netrapi/driving-session",
        json={
            "id": 1,
            "master_config_id": 1,
            "start_time": "2026-08-16T18:00:00Z",
        },
        headers=_HEADERS,
    )
    assert session.status_code == 200
    created = ingest_client.post(
        "/api/netrapi/trip-segment", json=_PAYLOAD, headers=_HEADERS
    )
    assert created.status_code == 200
    with get_session() as db:
        row = db.get(TripSegment, 3)
        assert row is not None
        row.s3_key = "stale"
        row.s3_stored = True
        db.add(row)
        db.commit()
    again = ingest_client.post(
        "/api/netrapi/trip-segment",
        json={**_PAYLOAD, "s3_key": "client-should-not-stick", "s3_stored": True},
        headers=_HEADERS,
    )
    assert again.status_code == 200
    body = again.json()
    assert body["s3_key"] == "stale"
    assert body["s3_stored"] is True
    assert body["init_local_deleted"] is None
    with get_session() as db:
        row = db.get(TripSegment, 3)
        assert row is not None
        assert row.s3_key == "stale"
        assert row.s3_stored is True
        assert row.file_size_bytes is None


def test_upsert_preserves_init_local_deleted_and_keeps_path_cleared(
    ingest_client: TestClient,
) -> None:
    session = ingest_client.post(
        "/api/netrapi/driving-session",
        json={
            "id": 1,
            "master_config_id": 1,
            "start_time": "2026-08-16T18:00:00Z",
        },
        headers=_HEADERS,
    )
    assert session.status_code == 200
    created = ingest_client.post(
        "/api/netrapi/trip-segment",
        json={**_PAYLOAD, "file_size_bytes": 99},
        headers=_HEADERS,
    )
    assert created.status_code == 200
    assert created.json()["file_size_bytes"] == 99
    deleted = ingest_client.post(
        "/api/netrapi/confirm-local-delete",
        json={"trip_segment_id": 3},
        headers=_HEADERS,
    )
    assert deleted.status_code == 200
    again = ingest_client.post(
        "/api/netrapi/trip-segment",
        json={**_PAYLOAD, "local_path": "/tmp/should-not-restore.mp4"},
        headers=_HEADERS,
    )
    assert again.status_code == 200
    body = again.json()
    assert body["init_local_deleted"] is True
    assert body["local_path"] is None
    assert body["file_size_bytes"] == 99
