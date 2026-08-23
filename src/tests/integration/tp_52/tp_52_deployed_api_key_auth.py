"""
TP-52: Deployed backend API-key authentication (integration).

Same contract as local TP-42, against Render:
GET /health with no key succeeds; POST /api/netrapi/driving-event without
a key or with a wrong key is 401; the same POST with a valid X-API-Key
is accepted (session is primed first).

Needs ``NETRAPI_API_KEY`` (and optional ``NETRAPI_API_URL``) in
``src/main/edge/.env`` matching Render. Does not use backend ``.env``.

Usage (from repo root, venv with httpx):

    python src/tests/integration/tp_52/tp_52_deployed_api_key_auth.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import (  # noqa: E402
    SEEDED_MASTER_CONFIG_ID,
    apply_edge_ingest_auth,
    configure_import_path,
    driving_event_payload,
    http_json,
    iso_z,
    wait_health,
)


def _print(label: str, response) -> None:
    print(f"  {label} -> {response.status_code}", flush=True)
    text = (response.text or "").strip()
    if not text:
        return
    try:
        print(json.dumps(response.json(), indent=2), flush=True)
    except Exception:
        print(text[:500], flush=True)


def main() -> int:
    configure_import_path()
    print("TP-52: Deployed backend API-key authentication", flush=True)
    print("  1. GET /health without an API key", flush=True)
    print("  2. POST /api/netrapi/driving-event without a key", flush=True)
    print("  3. POST the same route with an invalid key", flush=True)
    print("  4. POST driving-session then driving-event with a valid key", flush=True)

    try:
        origin = apply_edge_ingest_auth()
        print(f"  origin: {origin}", flush=True)
        from netrapi.backend_auth import ingest_headers

        wait_health(origin)
        run_id = 52_000_000 + int(time.time()) % 900_000
        start = datetime(2026, 8, 22, 19, 0, 0, tzinfo=timezone.utc)
        event_body = driving_event_payload(run_id, start)
        valid = {**ingest_headers(), "Accept": "application/json"}

        health = http_json(origin, "GET", "/health")
        _print("GET /health (no key)", health)
        if health.status_code != 200 or health.json().get("status") != "ok":
            raise RuntimeError(f"GET /health failed: {health.status_code} {health.text}")

        missing = http_json(
            origin, "POST", "/api/netrapi/driving-event", body=event_body
        )
        _print("POST driving-event (no key)", missing)
        if missing.status_code != 401:
            raise RuntimeError(
                f"missing key should be 401, got {missing.status_code}: {missing.text}"
            )

        invalid = http_json(
            origin,
            "POST",
            "/api/netrapi/driving-event",
            headers={"X-API-Key": "wrong-key"},
            body=event_body,
        )
        _print("POST driving-event (wrong key)", invalid)
        if invalid.status_code != 401:
            raise RuntimeError(
                f"invalid key should be 401, got {invalid.status_code}: {invalid.text}"
            )

        session = http_json(
            origin,
            "POST",
            "/api/netrapi/driving-session",
            headers=valid,
            body={
                "id": run_id,
                "master_config_id": SEEDED_MASTER_CONFIG_ID,
                "start_time": iso_z(start),
            },
        )
        _print("POST driving-session (valid X-API-Key)", session)
        if session.status_code != 200:
            raise RuntimeError(
                f"valid key session POST returned {session.status_code}: {session.text}"
            )

        ok = http_json(
            origin,
            "POST",
            "/api/netrapi/driving-event",
            headers=valid,
            body=event_body,
        )
        _print("POST driving-event (valid X-API-Key)", ok)
        if ok.status_code != 200:
            raise RuntimeError(
                f"valid key event POST returned {ok.status_code}: {ok.text}"
            )
        if ok.json().get("id") != run_id:
            raise RuntimeError(f"response id {ok.json().get('id')!r}")
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: deployed /health open; /api/netrapi/* requires X-API-Key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
