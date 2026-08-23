"""
TP-35: Local FastAPI health (integration).

Starts the ingest app via TestClient (same ASGI as uvicorn), GET /health,
prints the JSON, asserts status and UTC time.

Usage (from repo root, venv with fastapi + httpx + alembic):

    python src/tests/integration/tp_35/tp_35_local_fastapi_health.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
MAIN_DIR = REPO_ROOT / "src" / "main"
BACKEND_DIR = MAIN_DIR / "backend"
DB_DIR = MAIN_DIR / "db"
ALEMBIC_INI = DB_DIR / "alembic.ini"
OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"


def _configure_import_path() -> None:
    for entry in (str(MAIN_DIR), str(BACKEND_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


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
    print("TP-35: Local FastAPI health", flush=True)
    print("  1. SQLite schema (Alembic upgrade head)", flush=True)
    print("  2. GET /health", flush=True)

    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()

    url = _sqlite_url(OUTPUT_DB_PATH)
    os.environ["DATABASE_URL"] = url
    os.environ["NETRAPI_API_KEY"] = "local-test-netrapi-key"

    try:
        _init_schema(url)
        from fastapi.testclient import TestClient

        from app.main import app

        with TestClient(app) as client:
            response = client.get("/health")
        if response.status_code != 200:
            raise RuntimeError(f"GET /health returned {response.status_code}: {response.text}")
        body = response.json()
        print(json.dumps(body, indent=2), flush=True)
        if body.get("status") != "ok":
            raise RuntimeError(f"unexpected status: {body!r}")
        raw_time = body.get("time")
        if not isinstance(raw_time, str) or not raw_time:
            raise RuntimeError(f"missing time: {body!r}")
        datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: /health returned ok and UTC time")
    print(f"  inspect: {OUTPUT_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
