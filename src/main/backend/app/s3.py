from __future__ import annotations

from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import Settings, get_settings

CLIP_EXPIRES_SECONDS = 15 * 60
PUBLIC_CLIP_EXPIRES_SECONDS = 2 * 60
TRIP_EXPIRES_SECONDS = 60 * 60
DEFAULT_CONTENT_TYPE = "video/mp4"
_MONTH_ABBREV = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


class S3NotConfiguredError(RuntimeError):
    """Raised when AWS credentials or bucket are missing."""


def month_year_stamp(start_time: datetime) -> str:
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    utc = start_time.astimezone(timezone.utc)
    return f"{_MONTH_ABBREV[utc.month - 1]}-{utc.year}"


def media_object_key(
    *, kind: str, row_id: int, session_id: int, start_time: datetime
) -> str:
    if kind not in ("clip", "trip"):
        raise ValueError(f"unknown media kind {kind!r}")
    folder = "clips" if kind == "clip" else "trips"
    return (
        f"{month_year_stamp(start_time)}/driving_session_id_{session_id}/"
        f"{folder}/{kind}-{row_id}.mp4"
    )


def s3_settings_or_raise(
    settings: Settings | None = None,
) -> tuple[str, str, str, str]:
    settings = settings or get_settings()
    key_id = (settings.aws_access_key_id or "").strip()
    secret = (settings.aws_secret_access_key or "").strip()
    region = (settings.aws_region or "").strip() or "us-east-2"
    bucket = (settings.aws_s3_bucket or "").strip()
    if not key_id or not secret or not bucket:
        raise S3NotConfiguredError(
            "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_S3_BUCKET are required"
        )
    return key_id, secret, region, bucket


def _client(settings: Settings | None = None):
    key_id, secret, region, _bucket = s3_settings_or_raise(settings)
    return boto3.client(
        "s3",
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=Config(signature_version="s3v4"),
    )


def presign_put(
    object_key: str,
    *,
    content_type: str = DEFAULT_CONTENT_TYPE,
    expires_in: int,
    settings: Settings | None = None,
) -> str:
    _key_id, _secret, _region, bucket = s3_settings_or_raise(settings)
    return _client(settings).generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )


def presign_get(
    object_key: str,
    *,
    expires_in: int,
    settings: Settings | None = None,
) -> str:
    _key_id, _secret, _region, bucket = s3_settings_or_raise(settings)
    return _client(settings).generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=expires_in,
        HttpMethod="GET",
    )


def head_object(object_key: str, *, settings: Settings | None = None) -> dict | None:
    _key_id, _secret, _region, bucket = s3_settings_or_raise(settings)
    try:
        return _client(settings).head_object(Bucket=bucket, Key=object_key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise


def head_bucket(*, settings: Settings | None = None) -> None:
    _key_id, _secret, _region, bucket = s3_settings_or_raise(settings)
    _client(settings).head_bucket(Bucket=bucket)
