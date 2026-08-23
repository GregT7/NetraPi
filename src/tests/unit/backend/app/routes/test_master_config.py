from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import select

from db.config_snapshot import edge_json_config_dir, payload_from_json_dir
from db.database import get_session
from db.models import MasterConfig, PreviewConfig

_HEADERS = {"X-API-Key": "unit-test-netrapi-key"}


def test_master_config_reuses_seeded_snapshot(ingest_client: TestClient) -> None:
    payload = payload_from_json_dir(edge_json_config_dir())
    first = ingest_client.post(
        "/api/netrapi/master-config", json=payload, headers=_HEADERS
    )
    second = ingest_client.post(
        "/api/netrapi/master-config", json=payload, headers=_HEADERS
    )
    assert first.status_code == 200
    assert first.json() == {"id": 1, "created": False}
    assert second.status_code == 200
    assert second.json() == {"id": 1, "created": False}
    with get_session() as session:
        assert len(session.exec(select(MasterConfig)).all()) == 1


def test_master_config_inserts_when_payload_differs(ingest_client: TestClient) -> None:
    payload = payload_from_json_dir(edge_json_config_dir())
    payload["preview"] = {**payload["preview"], "window_name": "API Changed"}
    response = ingest_client.post(
        "/api/netrapi/master-config", json=payload, headers=_HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["id"] != 1
    with get_session() as session:
        preview = session.exec(
            select(PreviewConfig).where(PreviewConfig.master_config_id == body["id"])
        ).one()
        assert preview.window_name == "API Changed"
    again = ingest_client.post(
        "/api/netrapi/master-config", json=payload, headers=_HEADERS
    )
    assert again.status_code == 200
    assert again.json() == {"id": body["id"], "created": False}


def test_master_config_requires_api_key(ingest_client: TestClient) -> None:
    payload = payload_from_json_dir(edge_json_config_dir())
    missing = ingest_client.post("/api/netrapi/master-config", json=payload)
    assert missing.status_code == 401
