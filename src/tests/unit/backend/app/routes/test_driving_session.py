from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.driving_session import router
from db.models import DrivingSession, MasterConfig

_PAYLOAD = {
    "id": 1,
    "master_config_id": 1,
    "start_time": "2026-08-16T18:00:00Z",
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


def test_unknown_master_config_returns_400() -> None:
    inner = MagicMock()
    inner.get.return_value = None
    with patch("app.routes.driving_session.get_session", return_value=_session_cm(inner)):
        response = _client().post(
            "/api/netrapi/driving-session", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "master_config_id 1 not found"


def test_creates_session_when_row_missing() -> None:
    inner = MagicMock()

    def _get(model, _id):
        if model is MasterConfig:
            return MagicMock()
        return None

    inner.get.side_effect = _get
    with patch("app.routes.driving_session.get_session", return_value=_session_cm(inner)):
        response = _client().post(
            "/api/netrapi/driving-session", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 200
    inner.add.assert_called_once()
    created = inner.add.call_args.args[0]
    assert isinstance(created, DrivingSession)
    assert created.id == 1
    assert created.master_config_id == 1
    inner.commit.assert_called_once()


def test_updates_existing_session() -> None:
    existing = DrivingSession(
        id=1,
        master_config_id=9,
        start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
        end_time=None,
    )
    inner = MagicMock()

    def _get(model, _id):
        if model is MasterConfig:
            return MagicMock()
        return existing

    inner.get.side_effect = _get
    with patch("app.routes.driving_session.get_session", return_value=_session_cm(inner)):
        response = _client().post(
            "/api/netrapi/driving-session", json=_PAYLOAD, headers=_HEADERS
        )
    assert response.status_code == 200
    inner.add.assert_not_called()
    assert existing.master_config_id == 1
    assert existing.start_time == datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone.utc)
    inner.commit.assert_called_once()
