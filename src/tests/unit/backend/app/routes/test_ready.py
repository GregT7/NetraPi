from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app

_HEADERS = {"X-API-Key": "unit-test-netrapi-key"}


def test_ready_ok(memory_database_url: str) -> None:
    with patch("app.routes.ready.head_bucket"):
        with TestClient(create_app()) as client:
            response = client.get("/api/netrapi/ready", headers=_HEADERS)
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "s3": "ok"}


def test_ready_s3_failure_returns_503(memory_database_url: str) -> None:
    with patch("app.routes.ready.head_bucket", side_effect=RuntimeError("bucket down")):
        with TestClient(create_app()) as client:
            response = client.get("/api/netrapi/ready", headers=_HEADERS)
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "ok"
    assert body["s3"] == "error"
    assert "bucket down" in body["detail"]["s3"]


def test_ready_db_failure_returns_503(memory_database_url: str) -> None:
    with patch("app.routes.ready.get_session", side_effect=RuntimeError("db down")):
        with patch("app.routes.ready.head_bucket"):
            with TestClient(create_app()) as client:
                response = client.get("/api/netrapi/ready", headers=_HEADERS)
    assert response.status_code == 503
    body = response.json()
    assert body["database"] == "error"
    assert "db down" in body["detail"]["database"]


def test_health_stays_cheap(memory_database_url: str) -> None:
    with patch("app.routes.ready.head_bucket") as head:
        with TestClient(create_app()) as client:
            response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    head.assert_not_called()
