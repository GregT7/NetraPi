from __future__ import annotations

import json
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import Settings, get_settings

CLIP_EXPIRES_SECONDS = 15 * 60
PUBLIC_CLIP_EXPIRES_SECONDS = 2 * 60
TRIP_EXPIRES_SECONDS = 60 * 60
DEFAULT_CONTENT_TYPE = "video/mp4"
JSON_CONTENT_TYPE = "application/json"
CLIP_VIDEO_NAME = "clip.mp4"
CLIP_AREAS_NAME = "areas.json"
CLIP_MOTION_NAME = "motion.json"
CLIP_TRANSITIONS_NAME = "transitions.json"
CLIP_SIDECAR_NAMES = (CLIP_AREAS_NAME, CLIP_MOTION_NAME, CLIP_TRANSITIONS_NAME)
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
    if kind == "clip":
        return (
            f"{month_year_stamp(start_time)}/driving_session_id_{session_id}/"
            f"{folder}/clip-{row_id}/{CLIP_VIDEO_NAME}"
        )
    return (
        f"{month_year_stamp(start_time)}/driving_session_id_{session_id}/"
        f"{folder}/{kind}-{row_id}.mp4"
    )


def is_directory_clip_key(object_key: str) -> bool:
    return object_key.endswith(f"/{CLIP_VIDEO_NAME}") and "/clips/clip-" in object_key


def clip_sidecar_key(video_key: str, filename: str) -> str | None:
    if filename not in CLIP_SIDECAR_NAMES:
        raise ValueError(f"unknown clip sidecar {filename!r}")
    if not is_directory_clip_key(video_key):
        return None
    return f"{video_key.rsplit('/', 1)[0]}/{filename}"


def clip_sidecar_keys(video_key: str) -> tuple[str, ...] | None:
    if not is_directory_clip_key(video_key):
        return None
    prefix = video_key.rsplit("/", 1)[0]
    return tuple(f"{prefix}/{name}" for name in CLIP_SIDECAR_NAMES)


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


def get_object_json(object_key: str, *, settings: Settings | None = None) -> dict | None:
    _key_id, _secret, _region, bucket = s3_settings_or_raise(settings)
    try:
        body = _client(settings).get_object(Bucket=bucket, Key=object_key)
        raw = body["Body"].read()
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def head_bucket(*, settings: Settings | None = None) -> None:
    _key_id, _secret, _region, bucket = s3_settings_or_raise(settings)
    _client(settings).head_bucket(Bucket=bucket)
