"""
TP-34: Local FastAPI smoke insert (driving-session) (integration).

POST /api/netrapi/driving-session JSON (no file) into SQLite, then read
the row back.

Usage (from repo root, venv with fastapi + httpx + alembic):

    python src/tests/integration/tp_34/tp_34_local_fastapi_driving_session.py
"""

from __future__ import annotations

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

SEEDED_MASTER_CONFIG_ID = 1
SMOKE_SESSION_ID = 1
SMOKE_START = datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone.utc)


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
    print("TP-34: Local FastAPI smoke insert (driving-session)", flush=True)
    print("  1. SQLite schema (Alembic upgrade head)", flush=True)
    print("  2. POST /api/netrapi/driving-session JSON", flush=True)
    print("  3. Read the driving_session row back", flush=True)

    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()

    url = _sqlite_url(OUTPUT_DB_PATH)
    os.environ["DATABASE_URL"] = url
    os.environ["NETRAPI_API_KEY"] = "local-test-netrapi-key"
    headers = {"X-API-Key": "local-test-netrapi-key"}

    try:
        _init_schema(url)
        from fastapi.testclient import TestClient
        from sqlmodel import select

        from app.main import app
        from db.database import get_session
        from db.models import DrivingSession

        payload = {
            "id": SMOKE_SESSION_ID,
            "master_config_id": SEEDED_MASTER_CONFIG_ID,
            "start_time": SMOKE_START.isoformat().replace("+00:00", "Z"),
        }
        with TestClient(app) as client:
            multipart = client.post(
                "/api/netrapi/driving-session",
                files={"file": ("clip.mp4", b"not-json", "video/mp4")},
                headers=headers,
            )
            if multipart.status_code < 400:
                raise RuntimeError(
                    f"multipart should be rejected, got {multipart.status_code}"
                )
            response = client.post(
                "/api/netrapi/driving-session",
                json=payload,
                headers=headers,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"POST driving-session returned {response.status_code}: {response.text}"
                )
            body = response.json()
            if body.get("id") != SMOKE_SESSION_ID:
                raise RuntimeError(f"response id {body.get('id')!r}")
            if body.get("master_config_id") != SEEDED_MASTER_CONFIG_ID:
                raise RuntimeError(f"response master_config_id {body.get('master_config_id')!r}")
            with get_session() as session:
                row = session.get(DrivingSession, SMOKE_SESSION_ID)
                if row is None:
                    row = session.exec(
                        select(DrivingSession).where(
                            DrivingSession.id == SMOKE_SESSION_ID
                        )
                    ).first()
                if row is None:
                    raise RuntimeError("driving_session row missing after POST")
                if row.master_config_id != SEEDED_MASTER_CONFIG_ID:
                    raise RuntimeError("stored master_config_id mismatch")
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: driving-session JSON upserted; no file body accepted")
    print(f"  inspect: {OUTPUT_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
