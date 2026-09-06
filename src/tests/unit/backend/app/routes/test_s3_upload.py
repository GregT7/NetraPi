from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.s3 import S3NotConfiguredError
from db.database import get_session
from db.models import Clip, TripSegment

_HEADERS = {"X-API-Key": "unit-test-netrapi-key"}
_SESSION = {
    "id": 1,
    "master_config_id": 1,
    "start_time": "2026-08-16T18:00:00Z",
}
_EVENT = {
    "id": 1,
    "driving_session_id": 1,
    "time": "2026-08-16T18:00:01Z",
    "clip": {
        "id": 10,
        "fps": 30,
        "order_number": 1,
        "num_frames": 60,
        "start_time": "2026-08-16T18:00:00Z",
        "end_time": "2026-08-16T18:00:02Z",
        "init_local_stored": True,
        "local_path": "/tmp/clip.mp4",
    },
    "auto_classification": {
        "kind": "auto",
        "classification_type_id": 2,
        "stage1_classification_type_id": 2,
        "stage2_classification_type_id": 3,
    },
}
_EXPECTED_KEY = "Aug-2026/driving_session_id_1/clips/clip-10/clip.mp4"
_EXPECTED_TRIP_KEY = "Aug-2026/driving_session_id_1/trips/trip-3.mp4"
_TRIP = {
    "id": 3,
    "driving_session_id": 1,
    "local_path": "/tmp/seg.mp4",
    "init_local_stored": True,
    "file_size_bytes": 9,
    "start_time": "2026-08-16T18:00:00Z",
    "end_time": "2026-08-16T18:05:00Z",
    "order_number": 3,
}


def _prime_clip(client: TestClient) -> None:
    session = client.post(
        "/api/netrapi/driving-session", json=_SESSION, headers=_HEADERS
    )
    assert session.status_code == 200
    event = client.post("/api/netrapi/driving-event", json=_EVENT, headers=_HEADERS)
    assert event.status_code == 200


def _prime_trip(client: TestClient) -> None:
    session = client.post(
        "/api/netrapi/driving-session", json=_SESSION, headers=_HEADERS
    )
    assert session.status_code == 200
    trip = client.post("/api/netrapi/trip-segment", json=_TRIP, headers=_HEADERS)
    assert trip.status_code == 200


def test_s3_upload_url_requires_xor(ingest_client: TestClient) -> None:
    response = ingest_client.post(
        "/api/netrapi/s3-upload-url", json={}, headers=_HEADERS
    )
    assert response.status_code == 400
    both = ingest_client.post(
        "/api/netrapi/s3-upload-url",
        json={"clip_id": 10, "trip_segment_id": 3},
        headers=_HEADERS,
    )
    assert both.status_code == 400


def test_s3_upload_url_404_when_clip_missing(ingest_client: TestClient) -> None:
    response = ingest_client.post(
        "/api/netrapi/s3-upload-url",
        json={"clip_id": 10},
        headers=_HEADERS,
    )
    assert response.status_code == 404


def test_s3_upload_url_503_when_aws_missing(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    with patch(
        "app.routes.s3_upload.presign_put",
        side_effect=S3NotConfiguredError("AWS missing"),
    ):
        response = ingest_client.post(
            "/api/netrapi/s3-upload-url",
            json={"clip_id": 10},
            headers=_HEADERS,
        )
    assert response.status_code == 503


def test_s3_upload_url_returns_stable_key(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    with patch(
        "app.routes.s3_upload.presign_put", return_value="https://s3.example/put"
    ) as presign:
        first = ingest_client.post(
            "/api/netrapi/s3-upload-url",
            json={"clip_id": 10},
            headers=_HEADERS,
        )
        second = ingest_client.post(
            "/api/netrapi/s3-upload-url",
            json={"clip_id": 10},
            headers=_HEADERS,
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["object_key"] == second.json()["object_key"] == _EXPECTED_KEY
    assert first.json()["method"] == "PUT"
    assert first.json()["url"] == "https://s3.example/put"
    assert len(first.json()["objects"]) == 4
    assert first.json()["objects"][0]["name"] == "clip.mp4"
    assert first.json()["objects"][1]["name"] == "areas.json"
    assert first.json()["objects"][2]["name"] == "motion.json"
    assert first.json()["objects"][3]["name"] == "transitions.json"
    assert presign.call_count == 8
    with get_session() as session:
        clip = session.get(Clip, 10)
        assert clip is not None
        assert clip.s3_stored is None


def test_s3_upload_url_uses_session_start_not_clip_start(
    ingest_client: TestClient,
) -> None:
    _prime_clip(ingest_client)
    with get_session() as session:
        clip = session.get(Clip, 10)
        assert clip is not None
        clip.start_time = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
        session.add(clip)
        session.commit()
    with patch(
        "app.routes.s3_upload.presign_put", return_value="https://s3.example/put"
    ):
        response = ingest_client.post(
            "/api/netrapi/s3-upload-url",
            json={"clip_id": 10},
            headers=_HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["object_key"] == _EXPECTED_KEY


def test_confirm_heads_then_updates(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    with patch(
        "app.routes.s3_upload.head_object",
        return_value={"ContentLength": 13},
    ):
        response = ingest_client.post(
            "/api/netrapi/confirm-s3-upload",
            json={"clip_id": 10, "object_key": _EXPECTED_KEY},
            headers=_HEADERS,
        )
    assert response.status_code == 200
    assert response.json() == {
        "object_key": _EXPECTED_KEY,
        "s3_stored": True,
        "clip_id": 10,
        "file_size_bytes": 13,
    }
    with get_session() as session:
        clip = session.get(Clip, 10)
        assert clip is not None
        assert clip.s3_key == _EXPECTED_KEY
        assert clip.s3_stored is True
        assert clip.file_size_bytes == 13


def test_confirm_trip_sets_file_size_bytes(ingest_client: TestClient) -> None:
    _prime_trip(ingest_client)
    with patch(
        "app.routes.s3_upload.head_object",
        return_value={"ContentLength": 4096},
    ):
        response = ingest_client.post(
            "/api/netrapi/confirm-s3-upload",
            json={"trip_segment_id": 3, "object_key": _EXPECTED_TRIP_KEY},
            headers=_HEADERS,
        )
    assert response.status_code == 200
    assert response.json() == {
        "object_key": _EXPECTED_TRIP_KEY,
        "s3_stored": True,
        "trip_segment_id": 3,
        "file_size_bytes": 4096,
    }
    with get_session() as session:
        row = session.get(TripSegment, 3)
        assert row is not None
        assert row.s3_key == _EXPECTED_TRIP_KEY
        assert row.s3_stored is True
        assert row.file_size_bytes == 4096


def test_confirm_missing_object_returns_400(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    with patch("app.routes.s3_upload.head_object", return_value=None):
        response = ingest_client.post(
            "/api/netrapi/confirm-s3-upload",
            json={"clip_id": 10, "object_key": _EXPECTED_KEY},
            headers=_HEADERS,
        )
    assert response.status_code == 400


def test_confirm_missing_sidecar_returns_400(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)

    def _head(object_key: str):
        if object_key.endswith("clip.mp4"):
            return {"ContentLength": 13}
        return None

    with patch("app.routes.s3_upload.head_object", side_effect=_head):
        response = ingest_client.post(
            "/api/netrapi/confirm-s3-upload",
            json={"clip_id": 10, "object_key": _EXPECTED_KEY},
            headers=_HEADERS,
        )
    assert response.status_code == 400
    assert "areas.json" in response.json()["detail"]
    _prime_clip(ingest_client)
    response = ingest_client.post(
        "/api/netrapi/confirm-s3-upload",
        json={"clip_id": 10, "object_key": "other.mp4"},
        headers=_HEADERS,
    )
    assert response.status_code == 400


def test_s3_routes_require_api_key(ingest_client: TestClient) -> None:
    missing = ingest_client.post("/api/netrapi/s3-upload-url", json={"clip_id": 10})
    assert missing.status_code == 401
    health = ingest_client.get("/health")
    assert health.status_code == 200


def test_confirm_503_when_aws_missing(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    with patch(
        "app.routes.s3_upload.head_object",
        side_effect=S3NotConfiguredError("AWS missing"),
    ):
        response = ingest_client.post(
            "/api/netrapi/confirm-s3-upload",
            json={"clip_id": 10, "object_key": _EXPECTED_KEY},
            headers=_HEADERS,
        )
    assert response.status_code == 503


def test_s3_download_url_400_when_not_confirmed(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    response = ingest_client.post(
        "/api/netrapi/s3-download-url",
        json={"clip_id": 10},
        headers=_HEADERS,
    )
    assert response.status_code == 400


def test_s3_download_url_returns_get(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    with patch(
        "app.routes.s3_upload.head_object",
        return_value={"ContentLength": 13},
    ):
        confirmed = ingest_client.post(
            "/api/netrapi/confirm-s3-upload",
            json={"clip_id": 10, "object_key": _EXPECTED_KEY},
            headers=_HEADERS,
        )
    assert confirmed.status_code == 200
    with patch(
        "app.routes.s3_upload.presign_get", return_value="https://s3.example/get"
    ) as presign:
        response = ingest_client.post(
            "/api/netrapi/s3-download-url",
            json={"clip_id": 10},
            headers=_HEADERS,
        )
    assert response.status_code == 200
    assert response.json() == {
        "url": "https://s3.example/get",
        "object_key": _EXPECTED_KEY,
        "method": "GET",
        "clip_id": 10,
    }
    presign.assert_called_once()


def test_s3_download_url_requires_api_key(ingest_client: TestClient) -> None:
    missing = ingest_client.post("/api/netrapi/s3-download-url", json={"clip_id": 10})
    assert missing.status_code == 401


def test_confirm_local_delete_clip(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    response = ingest_client.post(
        "/api/netrapi/confirm-local-delete",
        json={"clip_id": 10},
        headers=_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {
        "init_local_deleted": True,
        "local_path": None,
        "clip_id": 10,
    }
    with get_session() as db:
        row = db.get(Clip, 10)
        assert row is not None
        assert row.init_local_deleted is True
        assert row.local_path is None
        assert row.s3_stored is None


def test_confirm_local_delete_trip(ingest_client: TestClient) -> None:
    _prime_trip(ingest_client)
    response = ingest_client.post(
        "/api/netrapi/confirm-local-delete",
        json={"trip_segment_id": 3},
        headers=_HEADERS,
    )
    assert response.status_code == 200
    assert response.json() == {
        "init_local_deleted": True,
        "local_path": None,
        "trip_segment_id": 3,
    }
    with get_session() as db:
        row = db.get(TripSegment, 3)
        assert row is not None
        assert row.init_local_deleted is True
        assert row.local_path is None
        assert row.file_size_bytes == 9


def test_confirm_local_delete_requires_xor(ingest_client: TestClient) -> None:
    response = ingest_client.post(
        "/api/netrapi/confirm-local-delete", json={}, headers=_HEADERS
    )
    assert response.status_code == 400
