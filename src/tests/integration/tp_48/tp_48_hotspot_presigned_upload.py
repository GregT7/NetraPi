"""
TP-48: Presigned upload over hotspot/mobile data (integration).

From this machine (on hotspot/cellular), authenticate to a reachable
FastAPI origin, POST s3-upload-url, PUT bytes to that URL (no AWS keys),
then confirm. Inspection HEAD uses backend .env (admin), not the client path.

Set NETRAPI_API_URL to a backend reachable from this network (LAN uvicorn
--host 0.0.0.0, tunnel, or deployed preview). Loopback is rejected unless
NETRAPI_TP48_ALLOW_LOOPBACK=1.

Usage (from repo root, venv with httpx + boto3):

    python src/tests/integration/tp_48/tp_48_hotspot_presigned_upload.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
MAIN_DIR = REPO_ROOT / "src" / "main"
BACKEND_DIR = MAIN_DIR / "backend"

SEEDED_MASTER_CONFIG_ID = 1
SMOKE_START = datetime(2026, 8, 22, 18, 0, 0, tzinfo=timezone.utc)
BODY = b"netrapi-tp-48\n"


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
        return settings
    finally:
        if saved_url is not None:
            os.environ["DATABASE_URL"] = saved_url
        if saved_key is not None:
            os.environ["NETRAPI_API_KEY"] = saved_key
        get_settings.cache_clear()


def _api_origin() -> str:
    raw = (os.environ.get("NETRAPI_API_URL") or "").strip().rstrip("/")
    if not raw:
        raise RuntimeError(
            "NETRAPI_API_URL is not set. Point it at a FastAPI origin reachable "
            "from this hotspot (not AWS). Example: http://192.168.0.12:8000"
        )
    host = (urlparse(raw).hostname or "").lower()
    allow_loopback = (os.environ.get("NETRAPI_TP48_ALLOW_LOOPBACK") or "").strip() == "1"
    if host in {"127.0.0.1", "localhost", "::1"} and not allow_loopback:
        raise RuntimeError(
            "NETRAPI_API_URL is loopback. TP-48 needs a backend reachable from "
            "hotspot/mobile data. Bind uvicorn --host 0.0.0.0 and use the LAN "
            "IP, or a tunnel/deployed preview. Set NETRAPI_TP48_ALLOW_LOOPBACK=1 "
            "only for a local dry run."
        )
    return raw


def _s3_client(settings):
    key_id = (settings.aws_access_key_id or "").strip()
    secret = (settings.aws_secret_access_key or "").strip()
    region = (settings.aws_region or "").strip() or "us-east-2"
    bucket = (settings.aws_s3_bucket or "").strip()
    if not key_id or not secret or not bucket:
        raise RuntimeError(
            "missing AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or AWS_S3_BUCKET"
        )
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=Config(signature_version="s3v4"),
    )
    return client, bucket


def main() -> int:
    _configure_import_path()
    print("TP-48: Presigned upload over hotspot/mobile data", flush=True)
    print("  1. GET /health on NETRAPI_API_URL", flush=True)
    print("  2. Client JSON: session, event, s3-upload-url, confirm", flush=True)
    print("  3. Client PUT to the issued S3 URL (no AWS keys)", flush=True)

    s3 = None
    bucket = None
    object_key = None
    try:
        settings = _load_backend_settings()
        origin = _api_origin()
        run_id = 48_000_000 + int(time.time()) % 900_000
        headers = {
            "X-API-Key": settings.netrapi_api_key,
            "Accept": "application/json",
        }
        print(f"  origin: {origin}", flush=True)
        print(
            "  reminder: run this while the client network is hotspot/cellular",
            flush=True,
        )
        with httpx.Client(base_url=origin, timeout=30.0) as client:
            health = client.get("/health")
            if health.status_code != 200:
                raise RuntimeError(
                    f"/health returned {health.status_code}: {health.text}"
                )
            session = client.post(
                "/api/netrapi/driving-session",
                json={
                    "id": run_id,
                    "master_config_id": SEEDED_MASTER_CONFIG_ID,
                    "start_time": _iso_z(SMOKE_START),
                },
                headers=headers,
            )
            if session.status_code != 200:
                raise RuntimeError(
                    f"POST driving-session returned {session.status_code}: "
                    f"{session.text}"
                )
            event = client.post(
                "/api/netrapi/driving-event",
                json={
                    "id": run_id,
                    "driving_session_id": run_id,
                    "time": _iso_z(SMOKE_START),
                    "clip": {
                        "id": run_id,
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
                headers=headers,
            )
            if event.status_code != 200:
                raise RuntimeError(
                    f"POST driving-event returned {event.status_code}: "
                    f"{event.text}"
                )
            issued = client.post(
                "/api/netrapi/s3-upload-url",
                json={"clip_id": run_id},
                headers=headers,
            )
            if issued.status_code != 200:
                raise RuntimeError(
                    f"s3-upload-url returned {issued.status_code}: {issued.text}"
                )
            issued_body = issued.json()
            put_url = issued_body.get("url")
            object_key = issued_body.get("object_key")
            if not put_url or not object_key:
                raise RuntimeError(f"s3-upload-url missing url/object_key: {issued_body!r}")
            if issued_body.get("method") != "PUT":
                raise RuntimeError(f"method {issued_body.get('method')!r}")
            put = httpx.put(
                put_url,
                content=BODY,
                headers={"Content-Type": "video/mp4"},
                timeout=60.0,
            )
            if put.status_code not in {200, 204}:
                raise RuntimeError(
                    f"presigned PUT returned {put.status_code}: {put.text}"
                )
            confirmed = client.post(
                "/api/netrapi/confirm-s3-upload",
                json={"clip_id": run_id, "object_key": object_key},
                headers=headers,
            )
            if confirmed.status_code != 200:
                raise RuntimeError(
                    f"confirm-s3-upload returned {confirmed.status_code}: "
                    f"{confirmed.text}"
                )
            if confirmed.json().get("s3_stored") is not True:
                raise RuntimeError(f"unexpected confirm body: {confirmed.json()!r}")

        s3, bucket = _s3_client(settings)
        head = s3.head_object(Bucket=bucket, Key=object_key)
        if head.get("ContentLength") != len(BODY):
            raise RuntimeError(
                f"S3 content_length {head.get('ContentLength')!r}"
            )
        print(f"  clip {run_id} -> {object_key}", flush=True)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        if s3 is not None and bucket and object_key:
            try:
                s3.delete_object(Bucket=bucket, Key=object_key)
            except Exception:
                pass

    print("PASS: presigned PUT+confirm succeeded from this client network")
    print("  client used no permanent AWS keys (only the issued URL)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
