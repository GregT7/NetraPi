"""
TP-36: Local FastAPI smoke insert (driving-event) (integration).

POSTs a session (TP-34 shape), then POST /api/netrapi/driving-event JSON
(no file) into SQLite and reads event + clip + auto classification back.
Alembic 0002 seeds classification_type.

Usage (from repo root, venv with fastapi + httpx + alembic):

    python src/tests/integration/tp_36/tp_36_local_fastapi_driving_event.py
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

SEEDED_MASTER_CONFIG_ID = 1
SMOKE_SESSION_ID = 1
SMOKE_EVENT_ID = 10
SMOKE_CLIP_ID = 10
SMOKE_START = datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone.utc)
SMOKE_EVENT_TIME = datetime(2026, 8, 16, 18, 12, 4, tzinfo=timezone.utc)
SMOKE_CLIP_START = datetime(2026, 8, 16, 18, 11, 54, tzinfo=timezone.utc)
SMOKE_CLIP_END = datetime(2026, 8, 16, 18, 12, 9, tzinfo=timezone.utc)

# Alembic 0002: rolling-stop, rolling-or-run-through
FINAL_TYPE_ID = 2
STAGE1_TYPE_ID = 4
STAGE2_TYPE_ID = 2


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
    config = Config(str(ALEMBIC_INI))
    command.upgrade(config, "head")


def main() -> int:
    _configure_import_path()
    print("TP-36: Local FastAPI smoke insert (driving-event)", flush=True)
    print("  1. SQLite schema (Alembic upgrade head, includes 0002 types)", flush=True)
    print("  2. POST /api/netrapi/driving-session JSON", flush=True)
    print("  3. POST /api/netrapi/driving-event JSON (no file)", flush=True)
    print("  4. Read event, clip, classification rows", flush=True)

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
        from db.models import AutoClassification, Classification, Clip, Event

        session_payload = {
            "id": SMOKE_SESSION_ID,
            "master_config_id": SEEDED_MASTER_CONFIG_ID,
            "start_time": _iso_z(SMOKE_START),
        }
        event_payload = {
            "id": SMOKE_EVENT_ID,
            "driving_session_id": SMOKE_SESSION_ID,
            "time": _iso_z(SMOKE_EVENT_TIME),
            "clip": {
                "id": SMOKE_CLIP_ID,
                "fps": 30,
                "order_number": 1,
                "num_frames": 450,
                "start_time": _iso_z(SMOKE_CLIP_START),
                "end_time": _iso_z(SMOKE_CLIP_END),
                "init_local_stored": True,
            },
            "auto_classification": {
                "kind": "auto",
                "classification_type_id": FINAL_TYPE_ID,
                "stage1_classification_type_id": STAGE1_TYPE_ID,
                "stage2_classification_type_id": STAGE2_TYPE_ID,
            },
        }
        with TestClient(app) as client:
            primed = client.post(
                "/api/netrapi/driving-session",
                json=session_payload,
                headers=headers,
            )
            if primed.status_code != 200:
                raise RuntimeError(
                    f"POST driving-session returned {primed.status_code}: {primed.text}"
                )
            multipart = client.post(
                "/api/netrapi/driving-event",
                files={"file": ("clip.mp4", b"not-json", "video/mp4")},
                headers=headers,
            )
            if multipart.status_code < 400:
                raise RuntimeError(
                    f"multipart should be rejected, got {multipart.status_code}"
                )
            response = client.post(
                "/api/netrapi/driving-event",
                json=event_payload,
                headers=headers,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"POST driving-event returned {response.status_code}: {response.text}"
                )
            body = response.json()
            print(json.dumps(body, indent=2), flush=True)
            if body.get("id") != SMOKE_EVENT_ID:
                raise RuntimeError(f"response id {body.get('id')!r}")
            if body.get("clip_id") != SMOKE_CLIP_ID:
                raise RuntimeError(f"response clip_id {body.get('clip_id')!r}")

            with get_session() as db:
                event = db.get(Event, SMOKE_EVENT_ID)
                if event is None:
                    raise RuntimeError("event row missing after POST")
                if event.driving_session_id != SMOKE_SESSION_ID:
                    raise RuntimeError("stored driving_session_id mismatch")
                clip = db.get(Clip, SMOKE_CLIP_ID)
                if clip is None:
                    raise RuntimeError("clip row missing after POST")
                if clip.event_id != SMOKE_EVENT_ID:
                    raise RuntimeError("clip.event_id mismatch")
                if clip.s3_key is not None or clip.s3_stored is not None:
                    raise RuntimeError(
                        f"s3 fields must stay null, got s3_key={clip.s3_key!r} "
                        f"s3_stored={clip.s3_stored!r}"
                    )
                if clip.init_local_stored is not True:
                    raise RuntimeError("clip.init_local_stored mismatch")
                classification = db.exec(
                    select(Classification).where(
                        Classification.event_id == SMOKE_EVENT_ID,
                        Classification.kind == "auto",
                    )
                ).first()
                if classification is None:
                    raise RuntimeError("auto classification row missing")
                if classification.classification_type_id != FINAL_TYPE_ID:
                    raise RuntimeError("classification_type_id mismatch")
                auto = db.exec(
                    select(AutoClassification).where(
                        AutoClassification.classification_id == classification.id
                    )
                ).first()
                if auto is None:
                    raise RuntimeError("auto_classification row missing")
                if auto.stage1_classification_type_id != STAGE1_TYPE_ID:
                    raise RuntimeError("stage1 type mismatch")
                if auto.stage2_classification_type_id != STAGE2_TYPE_ID:
                    raise RuntimeError("stage2 type mismatch")
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: driving-event JSON upserted; clip s3 flags null; no file body")
    print(f"  inspect: {OUTPUT_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
