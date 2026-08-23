from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
import pytest

from app.main import app, create_app
from db import database as database


def _route_paths(application) -> set[str]:
    return {getattr(route, "path", "") for route in application.routes}


def test_module_app_is_ingest_factory_instance():
    assert app.title == "NetraPi ingest"
    assert app is not create_app()


def test_create_app_registers_health_and_ingest_routes():
    application = create_app()
    paths = _route_paths(application)
    assert "/health" in paths
    assert "/api/netrapi/driving-session" in paths
    assert "/api/netrapi/master-config" in paths
    assert "/api/netrapi/trip-segment" in paths
    assert "/api/netrapi/driving-event" in paths
    assert "/api/netrapi/s3-upload-url" in paths
    assert "/api/netrapi/confirm-s3-upload" in paths
    assert "/api/netrapi/s3-download-url" in paths


def test_create_app_registers_s3_routes():
    paths = _route_paths(create_app())
    assert "/api/netrapi/s3-upload-url" in paths
    assert "/api/netrapi/confirm-s3-upload" in paths
    assert "/api/netrapi/s3-download-url" in paths


def test_lifespan_inits_and_disposes_engine(memory_database_url: str) -> None:
    application = create_app()
    with TestClient(application):
        assert database._engine is not None
        assert str(database._engine.url) == memory_database_url
    assert database._engine is None


def test_health_through_app(memory_database_url: str) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    datetime.fromisoformat(body["time"].replace("Z", "+00:00"))


def test_docs_enabled_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    paths = _route_paths(create_app())
    assert "/docs" in paths
    assert "/redoc" in paths
    assert "/openapi.json" in paths


def test_docs_disabled_on_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    paths = _route_paths(create_app())
    assert "/docs" not in paths
    assert "/redoc" not in paths
    assert "/openapi.json" not in paths
