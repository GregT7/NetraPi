"""
TP-43: s3-upload-url issuance and edge PUT (integration).

Authenticated JSON POST returns a time-limited S3 PUT URL. The client PUTs
bytes to that URL (no AWS keys). The object lands at the assigned key.
SQLite s3_stored stays null until confirm (TP-47).

Usage (from repo root, venv with fastapi + httpx + boto3 + alembic):

    python src/tests/integration/tp_43/tp_43_s3_upload_url.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

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
BODY = b"netrapi-tp-43\n"
EXPECTED_KEY = "Aug-2026/driving_session_id_1/clips/clip-10/clip.mp4"
JSON_BODY = b'{"schema_version":1,"points":[]}\n'


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


def _s3_client():
    from app.config import get_settings

    settings = get_settings()
    key_id = (settings.aws_access_key_id or "").strip()
    secret = (settings.aws_secret_access_key or "").strip()
    region = (settings.aws_region or "").strip() or "us-east-2"
    bucket = (settings.aws_s3_bucket or "").strip()
    if not key_id or not secret or not bucket:
        raise RuntimeError(
            "missing AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or AWS_S3_BUCKET"
        )
    import boto3

    return boto3.client(
        "s3",
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name=region,
    ), bucket


def _put_issued_objects(body: dict) -> list[str]:
    objects = body.get("objects")
    if not isinstance(objects, list) or not objects:
        objects = [
            {
                "url": body.get("url"),
                "object_key": body.get("object_key"),
                "content_type": "video/mp4",
            }
        ]
    keys: list[str] = []
    for item in objects:
        content_type = str(item.get("content_type") or "video/mp4")
        payload = BODY if content_type.startswith("video/") else JSON_BODY
        put = httpx.put(
            item["url"],
            content=payload,
            headers={"Content-Type": content_type},
            timeout=30.0,
        )
        if put.status_code not in {200, 204}:
            raise RuntimeError(
                f"presigned PUT returned {put.status_code}: {put.text}"
            )
        keys.append(str(item.get("object_key")))
    return keys


def main() -> int:
    _configure_import_path()
    print("TP-43: s3-upload-url issuance and edge PUT", flush=True)
    print("  1. Authenticated POST /api/netrapi/s3-upload-url (JSON, no file)", flush=True)
    print("  2. Client PUT to the returned URL (no AWS keys)", flush=True)
    print("  3. Object exists at object_key; s3_stored still null", flush=True)

    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()

    url = _sqlite_url(OUTPUT_DB_PATH)
    os.environ["DATABASE_URL"] = url
    os.environ["NETRAPI_API_KEY"] = TEST_API_KEY
    s3 = None
    bucket = None
    object_key = None
    uploaded_keys: list[str] = []
    try:
        _init_schema(url)
        from fastapi.testclient import TestClient

        from app.config import get_settings
        from app.main import app
        from db.database import get_session
        from db.models import Clip

        get_settings.cache_clear()
        s3, bucket = _s3_client()
        with TestClient(app) as client:
            _prime_clip(client)
            issued = client.post(
                "/api/netrapi/s3-upload-url",
                json={"clip_id": SMOKE_CLIP_ID},
                headers=HEADERS,
            )
            if issued.status_code != 200:
                raise RuntimeError(
                    f"s3-upload-url returned {issued.status_code}: {issued.text}"
                )
            body = issued.json()
            object_key = body.get("object_key")
            print(
                json.dumps(
                    {"object_key": object_key, "method": body.get("method")},
                    indent=2,
                ),
                flush=True,
            )
            if body.get("method") != "PUT":
                raise RuntimeError(f"method {body.get('method')!r}")
            if object_key != EXPECTED_KEY:
                raise RuntimeError(f"object_key {object_key!r}")
            uploaded_keys = _put_issued_objects(body)
            head = s3.head_object(Bucket=bucket, Key=object_key)
            if head.get("ContentLength") != len(BODY):
                raise RuntimeError(
                    f"unexpected content_length: {head.get('ContentLength')!r}"
                )
            with get_session() as db:
                clip = db.get(Clip, SMOKE_CLIP_ID)
                if clip is None:
                    raise RuntimeError("clip row missing")
                if clip.s3_stored is not None or clip.s3_key is not None:
                    raise RuntimeError(
                        f"s3 flags must stay null until confirm, "
                        f"got s3_key={clip.s3_key!r} s3_stored={clip.s3_stored!r}"
                    )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        if s3 is not None and bucket:
            for key in uploaded_keys or ([object_key] if object_key else []):
                try:
                    s3.delete_object(Bucket=bucket, Key=key)
                except Exception:
                    pass

    print("PASS: presigned PUT succeeded; s3_stored still null")
    print(f"  inspect: {OUTPUT_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
