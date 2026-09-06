from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.public_limits import live_slot_count, reset_for_tests
from app.s3 import PUBLIC_CLIP_EXPIRES_SECONDS, S3NotConfiguredError

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
_EVENT_NEWER = {
    "id": 2,
    "driving_session_id": 1,
    "time": "2026-08-16T19:00:01Z",
    "clip": {
        "id": 11,
        "fps": 30,
        "order_number": 2,
        "num_frames": 60,
        "start_time": "2026-08-16T19:00:00Z",
        "end_time": "2026-08-16T19:00:02Z",
        "init_local_stored": True,
        "local_path": "/tmp/clip-11.mp4",
    },
    "auto_classification": {
        "kind": "auto",
        "classification_type_id": 2,
        "stage1_classification_type_id": 2,
        "stage2_classification_type_id": 3,
    },
}
_EXPECTED_KEY_NEWER = "Aug-2026/driving_session_id_1/clips/clip-11/clip.mp4"
_PUBLIC = "/api/public/clip-download-url"


@pytest.fixture(autouse=True)
def _reset_public_limits() -> None:
    reset_for_tests()
    yield
    reset_for_tests()


def _prime_clip(client: TestClient) -> None:
    session = client.post(
        "/api/netrapi/driving-session", json=_SESSION, headers=_HEADERS
    )
    assert session.status_code == 200
    event = client.post("/api/netrapi/driving-event", json=_EVENT, headers=_HEADERS)
    assert event.status_code == 200


def _confirm_clip(client: TestClient) -> None:
    _prime_clip(client)
    with patch(
        "app.routes.s3_upload.head_object",
        return_value={"ContentLength": 13},
    ):
        confirmed = client.post(
            "/api/netrapi/confirm-s3-upload",
            json={"clip_id": 10, "object_key": _EXPECTED_KEY},
            headers=_HEADERS,
        )
    assert confirmed.status_code == 200


def test_public_mint_does_not_use_ingest_key(ingest_client: TestClient) -> None:
    missing = ingest_client.post(_PUBLIC, json={"clip_id": 10})
    assert missing.status_code != 401


def test_public_mint_404_when_clip_missing(ingest_client: TestClient) -> None:
    response = ingest_client.post(_PUBLIC, json={"clip_id": 10})
    assert response.status_code == 404


def test_public_mint_400_when_not_confirmed(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    response = ingest_client.post(_PUBLIC, json={"clip_id": 10})
    assert response.status_code == 400
    assert live_slot_count() == 0


def test_public_mint_returns_two_minute_get(ingest_client: TestClient) -> None:
    _confirm_clip(ingest_client)
    with patch(
        "app.routes.public_clip.presign_get",
        return_value="https://s3.example/public-get",
    ) as presign, patch(
        "app.routes.public_clip.get_object_json",
        return_value=None,
    ):
        response = ingest_client.post(_PUBLIC, json={"clip_id": 10})
    assert response.status_code == 200
    assert response.json() == {
        "url": "https://s3.example/public-get",
        "object_key": _EXPECTED_KEY,
        "method": "GET",
        "clip_id": 10,
        "expires_in": PUBLIC_CLIP_EXPIRES_SECONDS,
        "areas": None,
        "motion": None,
        "transitions": None,
        "live_urls": 1,
        "live_url_max": 20,
    }
    presign.assert_called_once()
    assert presign.call_args.kwargs["expires_in"] == 120
    assert live_slot_count() == 1


def test_public_mint_inlines_sidecar_json(ingest_client: TestClient) -> None:
    _confirm_clip(ingest_client)
    areas = {"schema_version": 1, "t0_s": 5.0, "sample_end_s": 10.0, "points": []}
    motion = {"schema_version": 1, "t0_s": 5.0, "sample_end_s": 10.0, "points": []}
    transitions = {
        "schema_version": 1,
        "classification": "rolling-stop",
        "states": [{"t": 0.0, "id": "Monitoring"}],
    }

    def _json(object_key: str):
        if object_key.endswith("areas.json"):
            return areas
        if object_key.endswith("motion.json"):
            return motion
        if object_key.endswith("transitions.json"):
            return transitions
        return None

    with patch(
        "app.routes.public_clip.presign_get",
        return_value="https://s3.example/public-get",
    ), patch(
        "app.routes.public_clip.get_object_json",
        side_effect=_json,
    ):
        response = ingest_client.post(_PUBLIC, json={"clip_id": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["areas"] == areas
    assert body["motion"] == motion
    assert body["transitions"] == transitions
    assert live_slot_count() == 1


def test_public_mint_503_releases_slot(ingest_client: TestClient) -> None:
    _confirm_clip(ingest_client)
    with patch(
        "app.routes.public_clip.presign_get",
        side_effect=S3NotConfiguredError("AWS missing"),
    ):
        response = ingest_client.post(_PUBLIC, json={"clip_id": 10})
    assert response.status_code == 503
    assert live_slot_count() == 0


def test_public_mint_rejects_21st_live_url(ingest_client: TestClient) -> None:
    _confirm_clip(ingest_client)
    with (
        patch("app.public_limits.PUBLIC_MAX_LIVE_URLS", 2),
        patch("app.public_limits.PUBLIC_MINT_RATE_MAX", 100),
        patch(
            "app.routes.public_clip.presign_get",
            return_value="https://s3.example/public-get",
        ),
        patch("app.routes.public_clip.get_object_json", return_value=None),
    ):
        first = ingest_client.post(_PUBLIC, json={"clip_id": 10})
        second = ingest_client.post(_PUBLIC, json={"clip_id": 10})
        third = ingest_client.post(_PUBLIC, json={"clip_id": 10})
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.headers.get("retry-after")
    assert live_slot_count() == 2


def test_public_mint_rate_limit_per_ip(ingest_client: TestClient) -> None:
    with patch("app.public_limits.PUBLIC_MINT_RATE_MAX", 2):
        first = ingest_client.post(_PUBLIC, json={"clip_id": 10})
        second = ingest_client.post(_PUBLIC, json={"clip_id": 10})
        third = ingest_client.post(_PUBLIC, json={"clip_id": 10})
    assert first.status_code == 404
    assert second.status_code == 404
    assert third.status_code == 429
    assert "Too many playback URL requests" in third.json()["detail"]


def test_public_list_empty_without_confirmed_clip(ingest_client: TestClient) -> None:
    _prime_clip(ingest_client)
    response = ingest_client.get("/api/public/clips")
    assert response.status_code == 200
    assert response.json() == {"clips": [], "live_urls": 0, "live_url_max": 20}


def test_public_list_returns_confirmed_clip(ingest_client: TestClient) -> None:
    _confirm_clip(ingest_client)
    response = ingest_client.get("/api/public/clips")
    assert response.status_code == 200
    assert response.json() == {
        "clips": [
            {
                "clip_id": 10,
                "id": "clip-10",
                "dateTime": "2026-08-16 06:00 PM",
                "label": "-",
                "classification": "Rolling Stop",
            }
        ],
        "live_urls": 0,
        "live_url_max": 20,
    }


def test_public_list_orders_newest_event_first(ingest_client: TestClient) -> None:
    _confirm_clip(ingest_client)
    newer = ingest_client.post(
        "/api/netrapi/driving-event", json=_EVENT_NEWER, headers=_HEADERS
    )
    assert newer.status_code == 200
    with patch(
        "app.routes.s3_upload.head_object",
        return_value={"ContentLength": 13},
    ):
        confirmed = ingest_client.post(
            "/api/netrapi/confirm-s3-upload",
            json={"clip_id": 11, "object_key": _EXPECTED_KEY_NEWER},
            headers=_HEADERS,
        )
    assert confirmed.status_code == 200
    response = ingest_client.get("/api/public/clips")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["clips"]] == ["clip-11", "clip-10"]
    assert response.json()["clips"][0]["dateTime"] == "2026-08-16 07:00 PM"


def test_public_list_label_comes_from_manual_classification(
    ingest_client: TestClient,
) -> None:
    _confirm_clip(ingest_client)
    labeled = ingest_client.post(
        "/api/netrapi/driving-event",
        json={
            **_EVENT,
            "manual_classification": {
                "classification_type_id": 1,
                "time_of_review": "2026-08-16T20:00:00Z",
            },
        },
        headers=_HEADERS,
    )
    assert labeled.status_code == 200
    response = ingest_client.get("/api/public/clips")
    assert response.status_code == 200
    row = response.json()["clips"][0]
    assert row["label"] == "Complete Stop"
    assert row["classification"] == "Rolling Stop"


def test_cors_allows_local_vite_preflight(ingest_client: TestClient) -> None:
    response = ingest_client.options(
        _PUBLIC,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_omits_unknown_origin(ingest_client: TestClient) -> None:
    response = ingest_client.options(
        _PUBLIC,
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "https://evil.example"
