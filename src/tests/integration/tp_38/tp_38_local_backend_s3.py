"""
TP-38: Local backend can reach S3 (integration).

Loads AWS settings from the backend `.env` (same Settings as FastAPI) and
PUTs a tiny object, HEADs it, then deletes it. No extra HTTP route.

Usage (from repo root, venv with boto3):

    python src/tests/integration/tp_38/tp_38_local_backend_s3.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
MAIN_DIR = REPO_ROOT / "src" / "main"
BACKEND_DIR = MAIN_DIR / "backend"
SMOKE_PREFIX = "_netrapi/tp-38"
BODY = b"netrapi-tp-38\n"


def _configure_import_path() -> None:
    for entry in (str(MAIN_DIR), str(BACKEND_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def main() -> int:
    _configure_import_path()
    print("TP-38: Local backend can reach S3", flush=True)
    print("  1. Load AWS settings from backend .env", flush=True)
    print("  2. PUT + HEAD a tiny object, then delete it", flush=True)

    try:
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
        finally:
            if saved_url is not None:
                os.environ["DATABASE_URL"] = saved_url
            if saved_key is not None:
                os.environ["NETRAPI_API_KEY"] = saved_key
            get_settings.cache_clear()
        key_id = _clean(settings.aws_access_key_id)
        secret = _clean(settings.aws_secret_access_key)
        region = _clean(settings.aws_region) or "us-east-2"
        bucket = _clean(settings.aws_s3_bucket)
        missing = [
            name
            for name, value in (
                ("AWS_ACCESS_KEY_ID", key_id),
                ("AWS_SECRET_ACCESS_KEY", secret),
                ("AWS_S3_BUCKET", bucket),
            )
            if not value
        ]
        if missing:
            raise RuntimeError("missing " + ", ".join(missing))

        import boto3

        object_key = f"{SMOKE_PREFIX}/{uuid4().hex}.txt"
        client = boto3.client(
            "s3",
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
            region_name=region,
        )
        client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=BODY,
            ContentType="text/plain",
        )
        head = client.head_object(Bucket=bucket, Key=object_key)
        deleted = False
        body = {
            "ok": True,
            "bucket": bucket,
            "key": object_key,
            "content_length": head.get("ContentLength"),
            "deleted": deleted,
        }
        print(json.dumps(body, indent=2), flush=True)
        if head.get("ContentLength") != len(BODY):
            raise RuntimeError(f"unexpected content_length: {head.get('ContentLength')!r}")
    except ModuleNotFoundError as exc:
        print(
            "FAIL: boto3 is missing. pip install boto3==1.35.99 "
            f"({exc})",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: backend PUT + HEAD succeeded against the private bucket")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
