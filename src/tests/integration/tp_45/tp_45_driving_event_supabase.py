"""
TP-45: driving-event persist to Supabase (integration).

Authenticated POST /api/netrapi/driving-event writes one event plus nested
children to Postgres (backend .env DATABASE_URL). JSON only. Cloud
counterpart of TP-36. Clip s3_key / s3_stored stay null.

Usage (from repo root, venv with fastapi + httpx + psycopg2):

    python src/tests/integration/tp_45/tp_45_driving_event_supabase.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
MAIN_DIR = REPO_ROOT / "src" / "main"
BACKEND_DIR = MAIN_DIR / "backend"

SEEDED_MASTER_CONFIG_ID = 1
FINAL_TYPE_ID = 2
STAGE1_TYPE_ID = 4
STAGE2_TYPE_ID = 2
SMOKE_START = datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone.utc)
SMOKE_EVENT_TIME = datetime(2026, 8, 16, 18, 12, 4, tzinfo=timezone.utc)
SMOKE_CLIP_START = datetime(2026, 8, 16, 18, 11, 54, tzinfo=timezone.utc)
SMOKE_CLIP_END = datetime(2026, 8, 16, 18, 12, 9, tzinfo=timezone.utc)


def _configure_import_path() -> None:
    for entry in (str(MAIN_DIR), str(BACKEND_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _load_backend_settings():
    from pydantic import ValidationError

    from app.config import Settings, get_settings

    saved_url = os.environ.pop("DATABASE_URL", None)
    saved_key = os.environ.pop("NETRAPI_API_KEY", None)
    try:
        get_settings.cache_clear()
        try:
            settings = Settings(_env_file=BACKEND_DIR / ".env")
        except ValidationError:
            raise RuntimeError(
                "src/main/backend/.env must set DATABASE_URL and NETRAPI_API_KEY"
            )
        url = (settings.database_url or "").strip()
        if not url.lower().startswith("postgresql"):
            raise RuntimeError(
                "backend .env DATABASE_URL must be the Supabase postgresql URI"
            )
        from sqlalchemy.engine import make_url

        host = (make_url(url).host or "").strip()
        if host.upper() == "HOST":
            raise RuntimeError(
                "backend .env DATABASE_URL still uses a placeholder host. "
                "Put the real Supabase postgresql+psycopg2 URI there."
            )
        return settings
    finally:
        if saved_url is not None:
            os.environ["DATABASE_URL"] = saved_url
        if saved_key is not None:
            os.environ["NETRAPI_API_KEY"] = saved_key
        get_settings.cache_clear()


def main() -> int:
    _configure_import_path()
    print("TP-45: driving-event persist to Supabase", flush=True)
    print("  1. POST /api/netrapi/driving-session JSON", flush=True)
    print("  2. POST /api/netrapi/driving-event JSON (no file)", flush=True)
    print("  3. Query Postgres for event, clip, classification", flush=True)

    try:
        from fastapi.testclient import TestClient
        from sqlmodel import select

        from app.config import get_settings
        from db.database import get_session
        from db.models import AutoClassification, Classification, Clip, Event

        settings = _load_backend_settings()
        run_id = 45_000_000 + int(time.time()) % 900_000
        os.environ["DATABASE_URL"] = settings.database_url
        os.environ["NETRAPI_API_KEY"] = settings.netrapi_api_key
        get_settings.cache_clear()

        from app.main import app

        headers = {"X-API-Key": settings.netrapi_api_key}
        session_payload = {
            "id": run_id,
            "master_config_id": SEEDED_MASTER_CONFIG_ID,
            "start_time": _iso_z(SMOKE_START),
        }
        event_payload = {
            "id": run_id,
            "driving_session_id": run_id,
            "time": _iso_z(SMOKE_EVENT_TIME),
            "clip": {
                "id": run_id,
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
                    f"POST driving-event returned {response.status_code}: "
                    f"{response.text}"
                )
            body = response.json()
            print(json.dumps(body, indent=2), flush=True)
            if body.get("id") != run_id:
                raise RuntimeError(f"response id {body.get('id')!r}")
            if body.get("clip_id") != run_id:
                raise RuntimeError(f"response clip_id {body.get('clip_id')!r}")

            with get_session() as db:
                event = db.get(Event, run_id)
                if event is None:
                    raise RuntimeError("Postgres event row missing after POST")
                if event.driving_session_id != run_id:
                    raise RuntimeError("stored driving_session_id mismatch")
                clip = db.get(Clip, run_id)
                if clip is None:
                    raise RuntimeError("Postgres clip row missing after POST")
                if clip.event_id != run_id:
                    raise RuntimeError("clip.event_id mismatch")
                if clip.s3_key is not None or clip.s3_stored is not None:
                    raise RuntimeError(
                        f"s3 fields must stay null, got s3_key={clip.s3_key!r} "
                        f"s3_stored={clip.s3_stored!r}"
                    )
                classification = db.exec(
                    select(Classification).where(
                        Classification.event_id == run_id,
                        Classification.kind == "auto",
                    )
                ).first()
                if classification is None:
                    raise RuntimeError("Postgres auto classification missing")
                auto = db.exec(
                    select(AutoClassification).where(
                        AutoClassification.classification_id == classification.id
                    )
                ).first()
                if auto is None:
                    raise RuntimeError("Postgres auto_classification missing")
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: driving-event JSON upserted to Postgres; clip s3 flags null")
    print(f"  inspect Postgres event/clip id {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
