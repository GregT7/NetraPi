"""
TP-44: Stable S3 object key generation (integration).

Two authenticated s3-upload-url calls for the same clip id return the same
object_key (month/session/clips/clip id). Durable reference is the key, not the URL.

Usage (from repo root, venv with fastapi + alembic):

    python src/tests/integration/tp_44/tp_44_stable_s3_object_key.py
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

TEST_API_KEY = "local-test-netrapi-key"
HEADERS = {"X-API-Key": TEST_API_KEY}
SEEDED_MASTER_CONFIG_ID = 1
SMOKE_SESSION_ID = 1
SMOKE_EVENT_ID = 10
SMOKE_CLIP_ID = 10
SMOKE_START = datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone.utc)
EXPECTED_KEY = "Aug-2026/driving_session_id_1/clips/clip-10/clip.mp4"


def _configure_import_path() -> None:
    for entry in (str(MAIN_DIR), str(BACKEND_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _init_schema(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")
    os.environ["DATABASE_URL"] = url
    from db.database import set_database_url_override

    set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def _prime_clip(client) -> None:
    session = client.post(
        "/api/netrapi/driving-session",
        json={
            "id": SMOKE_SESSION_ID,
            "master_config_id": SEEDED_MASTER_CONFIG_ID,
            "start_time": _iso_z(SMOKE_START),
        },
        headers=HEADERS,
    )
    if session.status_code != 200:
        raise RuntimeError(
            f"POST driving-session returned {session.status_code}: {session.text}"
        )
    event = client.post(
        "/api/netrapi/driving-event",
        json={
            "id": SMOKE_EVENT_ID,
            "driving_session_id": SMOKE_SESSION_ID,
            "time": _iso_z(SMOKE_START),
            "clip": {
                "id": SMOKE_CLIP_ID,
                "fps": 30,
                "order_number": 1,
                "num_frames": 60,
                "start_time": _iso_z(SMOKE_START),
                "end_time": _iso_z(SMOKE_START),
                "init_local_stored": True,
            },
            "auto_classification": {
                "kind": "auto",
                "classification_type_id": 2,
                "stage1_classification_type_id": 4,
                "stage2_classification_type_id": 2,
            },
        },
        headers=HEADERS,
    )
    if event.status_code != 200:
        raise RuntimeError(
            f"POST driving-event returned {event.status_code}: {event.text}"
        )


def main() -> int:
    _configure_import_path()
    print("TP-44: Stable S3 object key generation", flush=True)
    print("  1. POST s3-upload-url twice for the same clip id", flush=True)
    print(
        "  2. Keys match MMM-YYYY/driving_session_id_{id}/clips/clip-{id}.mp4",
        flush=True,
    )

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
        with TestClient(app) as client:
            _prime_clip(client)
            first = client.post(
                "/api/netrapi/s3-upload-url",
                json={"clip_id": SMOKE_CLIP_ID},
                headers=HEADERS,
            )
            second = client.post(
                "/api/netrapi/s3-upload-url",
                json={"clip_id": SMOKE_CLIP_ID},
                headers=HEADERS,
            )
            if first.status_code != 200:
                raise RuntimeError(
                    f"first s3-upload-url returned {first.status_code}: {first.text}"
                )
            if second.status_code != 200:
                raise RuntimeError(
                    f"second s3-upload-url returned {second.status_code}: {second.text}"
                )
            key_a = first.json().get("object_key")
            key_b = second.json().get("object_key")
            if key_a != key_b:
                raise RuntimeError(f"keys differ: {key_a!r} vs {key_b!r}")
            if key_a != EXPECTED_KEY:
                raise RuntimeError(f"object_key {key_a!r}")
            if first.json().get("url") == key_a:
                raise RuntimeError("durable reference must be object_key, not url")
            print(f"  object_key: {key_a}", flush=True)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: object keys are stable for a given clip identity")
    print(f"  inspect: {OUTPUT_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
