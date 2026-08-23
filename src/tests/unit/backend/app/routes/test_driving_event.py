from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select

from app.routes.driving_event import router
from db.database import get_session
from db.models import (
    ApproachFailReason,
    ApproachParameters,
    Classification,
    ClassificationType,
    Clip,
    DrivingSession,
    EventTripLocation,
    KnnParameter,
    ManualClassification,
)

_CLIP = {
    "id": 10,
    "fps": 30,
    "order_number": 1,
    "num_frames": 60,
    "start_time": "2026-08-16T18:00:00Z",
    "end_time": "2026-08-16T18:00:02Z",
    "init_local_stored": True,
    "local_path": "/tmp/clip.mp4",
    "file_size_bytes": 42,
}

_AUTO = {
    "kind": "auto",
    "classification_type_id": 2,
    "stage1_classification_type_id": 2,
    "stage2_classification_type_id": 3,
}

_PAYLOAD = {
    "id": 1,
    "driving_session_id": 1,
    "time": "2026-08-16T18:00:01Z",
    "clip": _CLIP,
    "auto_classification": _AUTO,
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


def test_rejects_non_auto_classification_kind() -> None:
    payload = {
        **_PAYLOAD,
        "auto_classification": {**_AUTO, "kind": "manual"},
    }
    response = _client().post(
        "/api/netrapi/driving-event", json=payload, headers=_HEADERS
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "auto_classification.kind must be 'auto'"


def test_unknown_driving_session_returns_400() -> None:
    inner = MagicMock()
    inner.get.return_value = None
    with patch("app.routes.driving_event.get_session", return_value=_session_cm(inner)):
        response = _client().post(
            "/api/netrapi/driving-event", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "driving_session 1 not found"


def test_unknown_classification_type_returns_400() -> None:
    inner = MagicMock()

    def _get(model, id_):
        if model is DrivingSession:
            return MagicMock()
        if model is ClassificationType:
            return None
        return None

    inner.get.side_effect = _get
    with patch("app.routes.driving_event.get_session", return_value=_session_cm(inner)):
        response = _client().post(
            "/api/netrapi/driving-event", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "classification_type 2 not found"


def _prime_session(client: TestClient) -> None:
    response = client.post(
        "/api/netrapi/driving-session",
        json={
            "id": 1,
            "master_config_id": 1,
            "start_time": "2026-08-16T18:00:00Z",
        },
        headers=_HEADERS,
    )
    assert response.status_code == 200


def test_minimal_payload_still_succeeds(ingest_client: TestClient) -> None:
    _prime_session(ingest_client)
    response = ingest_client.post(
        "/api/netrapi/driving-event", json=_PAYLOAD, headers=_HEADERS
    )
    assert response.status_code == 200
    with get_session() as session:
        assert session.exec(select(KnnParameter)).first() is None
        assert session.exec(select(ApproachParameters)).first() is None


def test_nested_children_persist(ingest_client: TestClient) -> None:
    _prime_session(ingest_client)
    trip = ingest_client.post(
        "/api/netrapi/trip-segment",
        json={
            "id": 3,
            "driving_session_id": 1,
            "local_path": "/tmp/seg.mp4",
            "init_local_stored": True,
            "start_time": "2026-08-16T18:00:00Z",
            "end_time": "2026-08-16T18:05:00Z",
            "order_number": 3,
        },
        headers=_HEADERS,
    )
    assert trip.status_code == 200
    payload = {
        **_PAYLOAD,
        "knn_parameters": [{"knn_feature_id": 2, "value": 0.12}],
        "approach_parameters": {
            "peak_area_pct": 8.0,
            "approach_duration_s": 2.5,
            "increasing_fraction": 0.9,
            "log_linear_r2": 0.8,
            "drop_duration_s": 0.4,
            "post_drop_holds": True,
            "fail_reasons": ["too-short"],
        },
        "event_trip_location": {
            "trip_segment_id": 3,
            "trip_offset_seconds": 12.5,
        },
        "manual_classification": {
            "classification_type_id": 5,
            "time_of_review": "2026-08-16T19:00:00Z",
        },
    }
    response = ingest_client.post(
        "/api/netrapi/driving-event", json=payload, headers=_HEADERS
    )
    assert response.status_code == 200
    with get_session() as session:
        knn = session.exec(select(KnnParameter)).one()
        assert knn.knn_feature_id == 2
        assert knn.value == 0.12
        approach = session.exec(select(ApproachParameters)).one()
        assert approach.approach_duration_s == 2.5
        reasons = session.exec(select(ApproachFailReason)).all()
        assert [row.reason for row in reasons] == ["too-short"]
        loc = session.exec(select(EventTripLocation)).one()
        assert loc.trip_segment_id == 3
        assert loc.trip_offset_seconds == 12.5
        manual = session.exec(
            select(Classification).where(Classification.kind == "manual")
        ).one()
        extra = session.exec(
            select(ManualClassification).where(
                ManualClassification.classification_id == manual.id
            )
        ).one()
        assert extra.time_of_review is not None


def test_trip_location_unknown_segment_returns_400(ingest_client: TestClient) -> None:
    _prime_session(ingest_client)
    payload = {
        **_PAYLOAD,
        "event_trip_location": {
            "trip_segment_id": 99,
            "trip_offset_seconds": 1.0,
        },
    }
    response = ingest_client.post(
        "/api/netrapi/driving-event", json=payload, headers=_HEADERS
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "trip_segment 99 not found"


def test_clip_upsert_keeps_existing_s3_flags(ingest_client: TestClient) -> None:
    _prime_session(ingest_client)
    first = ingest_client.post(
        "/api/netrapi/driving-event", json=_PAYLOAD, headers=_HEADERS
    )
    assert first.status_code == 200
    with get_session() as session:
        clip = session.get(Clip, 10)
        assert clip is not None
        clip.s3_key = "Aug-2026/driving_session_id_1/clips/clip-10.mp4"
        clip.s3_stored = True
        session.add(clip)
        session.commit()
    second = ingest_client.post(
        "/api/netrapi/driving-event", json=_PAYLOAD, headers=_HEADERS
    )
    assert second.status_code == 200
    with get_session() as session:
        clip = session.get(Clip, 10)
        assert clip is not None
        assert clip.s3_key == "Aug-2026/driving_session_id_1/clips/clip-10.mp4"
        assert clip.s3_stored is True
        assert clip.file_size_bytes == 42


def test_clip_upsert_keeps_init_local_deleted(ingest_client: TestClient) -> None:
    _prime_session(ingest_client)
    first = ingest_client.post(
        "/api/netrapi/driving-event", json=_PAYLOAD, headers=_HEADERS
    )
    assert first.status_code == 200
    deleted = ingest_client.post(
        "/api/netrapi/confirm-local-delete",
        json={"clip_id": 10},
        headers=_HEADERS,
    )
    assert deleted.status_code == 200
    second = ingest_client.post(
        "/api/netrapi/driving-event", json=_PAYLOAD, headers=_HEADERS
    )
    assert second.status_code == 200
    with get_session() as session:
        clip = session.get(Clip, 10)
        assert clip is not None
        assert clip.init_local_deleted is True
        assert clip.local_path is None
        assert clip.file_size_bytes == 42
