from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_does_not_require_api_key(memory_database_url: str) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ingest_without_api_key_returns_401(memory_database_url: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/netrapi/driving-session",
            json={
                "id": 1,
                "master_config_id": 1,
                "start_time": "2026-08-16T18:00:00Z",
            },
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_new_ingest_routes_require_api_key(memory_database_url: str) -> None:
    with TestClient(create_app()) as client:
        trip = client.post(
            "/api/netrapi/trip-segment",
            json={
                "id": 1,
                "driving_session_id": 1,
                "start_time": "2026-08-16T18:00:00Z",
                "end_time": "2026-08-16T18:05:00Z",
                "order_number": 1,
            },
        )
        master = client.post("/api/netrapi/master-config", json={})
        s3 = client.post("/api/netrapi/s3-upload-url", json={"clip_id": 1})
        download = client.post("/api/netrapi/s3-download-url", json={"clip_id": 1})
    assert trip.status_code == 401
    assert master.status_code == 401
    assert s3.status_code == 401
    assert download.status_code == 401


def test_ingest_with_wrong_api_key_returns_401(memory_database_url: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/netrapi/driving-session",
            json={
                "id": 1,
                "master_config_id": 1,
                "start_time": "2026-08-16T18:00:00Z",
            },
            headers={"X-API-Key": "wrong-key"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"
