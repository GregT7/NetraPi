"""
TP-42: Edge API-key authentication (integration).

GET /health without a key must succeed. POST /api/netrapi/driving-session
without a key or with a wrong key is rejected. The same POST with
X-API-Key matching NETRAPI_API_KEY is accepted.

Usage (from repo root, venv with fastapi + httpx + alembic):

    python src/tests/integration/tp_42/tp_42_edge_api_key_auth.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
MAIN_DIR = REPO_ROOT / "src" / "main"
BACKEND_DIR = MAIN_DIR / "backend"
DB_DIR = MAIN_DIR / "db"
ALEMBIC_INI = DB_DIR / "alembic.ini"
OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"

TEST_API_KEY = "local-test-netrapi-key"
SEEDED_MASTER_CONFIG_ID = 1
SMOKE_SESSION_ID = 1
SMOKE_START = datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone.utc)


def _configure_import_path() -> None:
    for entry in (str(MAIN_DIR), str(BACKEND_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _print_response(label: str, response) -> None:
    print(f"  {label} -> {response.status_code}", flush=True)
    text = (response.text or "").strip()
    if not text:
        return
    try:
        print(json.dumps(response.json(), indent=2), flush=True)
    except Exception:
        print(text, flush=True)


def _init_schema(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")
    os.environ["DATABASE_URL"] = url
    from db.database import set_database_url_override

    set_database_url_override(url)
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")


def main() -> int:
    _configure_import_path()
    print("TP-42: Edge API-key authentication", flush=True)
    print("  1. GET /health without an API key", flush=True)
    print("  2. POST /api/netrapi/driving-session without a key", flush=True)
    print("  3. POST the same route with an invalid key", flush=True)
    print("  4. POST the same route with a valid X-API-Key", flush=True)

    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()

    url = _sqlite_url(OUTPUT_DB_PATH)
    os.environ["DATABASE_URL"] = url
    os.environ["NETRAPI_API_KEY"] = TEST_API_KEY

    try:
        _init_schema(url)
        from fastapi.testclient import TestClient

        from app.config import get_settings
        from app.main import app

        get_settings.cache_clear()
        payload = {
            "id": SMOKE_SESSION_ID,
            "master_config_id": SEEDED_MASTER_CONFIG_ID,
            "start_time": SMOKE_START.isoformat().replace("+00:00", "Z"),
        }
        with TestClient(app) as client:
            health = client.get("/health")
            _print_response("GET /health (no key)", health)
            if health.status_code != 200:
                raise RuntimeError(
                    f"GET /health returned {health.status_code}: {health.text}"
                )
            if health.json().get("status") != "ok":
                raise RuntimeError(f"unexpected health: {health.json()!r}")

            missing = client.post("/api/netrapi/driving-session", json=payload)
            _print_response("POST driving-session (no key)", missing)
            if missing.status_code != 401:
                raise RuntimeError(
                    f"missing key should be 401, got {missing.status_code}: "
                    f"{missing.text}"
                )

            invalid = client.post(
                "/api/netrapi/driving-session",
                json=payload,
                headers={"X-API-Key": "wrong-key"},
            )
            _print_response("POST driving-session (wrong key)", invalid)
            if invalid.status_code != 401:
                raise RuntimeError(
                    f"invalid key should be 401, got {invalid.status_code}: "
                    f"{invalid.text}"
                )

            ok = client.post(
                "/api/netrapi/driving-session",
                json=payload,
                headers={"X-API-Key": TEST_API_KEY},
            )
            _print_response("POST driving-session (valid X-API-Key)", ok)
            if ok.status_code != 200:
                raise RuntimeError(
                    f"valid key POST returned {ok.status_code}: {ok.text}"
                )
            if ok.json().get("id") != SMOKE_SESSION_ID:
                raise RuntimeError(f"response id {ok.json().get('id')!r}")
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: /health open; /api/netrapi/* requires X-API-Key")
    print(f"  inspect: {OUTPUT_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
