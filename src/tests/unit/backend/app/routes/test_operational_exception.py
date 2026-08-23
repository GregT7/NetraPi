from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.operational_exception import router
from db.models import DrivingSession, OperationalException

_PAYLOAD = {
    "id": 7,
    "driving_session_id": 1,
    "message": "camera read failed",
    "time": "2026-08-16T18:00:00Z",
    "is_fatal": True,
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


def test_unknown_session_returns_400() -> None:
    inner = MagicMock()
    inner.get.return_value = None
    with patch(
        "app.routes.operational_exception.get_session", return_value=_session_cm(inner)
    ):
        response = _client().post(
            "/api/netrapi/operational-exception", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "driving_session 1 not found"


def test_creates_exception_when_row_missing() -> None:
    inner = MagicMock()

    def _get(model, _id):
        if model is DrivingSession:
            return MagicMock()
        return None

    inner.get.side_effect = _get
    with patch(
        "app.routes.operational_exception.get_session", return_value=_session_cm(inner)
    ):
        response = _client().post(
            "/api/netrapi/operational-exception", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 200
    created = inner.add.call_args.args[0]
    assert isinstance(created, OperationalException)
    assert created.id == 7
    assert created.is_fatal is True
    inner.commit.assert_called_once()


def test_operational_exception_roundtrip(ingest_client: TestClient) -> None:
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
    response = ingest_client.post(
        "/api/netrapi/operational-exception", json=_PAYLOAD, headers=_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["id"] == 7
    assert response.json()["is_fatal"] is True
