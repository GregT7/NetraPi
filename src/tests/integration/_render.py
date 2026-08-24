"""Shared helpers for Sprint 7 tests against the deployed Render backend."""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_ORIGIN = "https://netrapi.onrender.com"
SEEDED_MASTER_CONFIG_ID = 1
# Render free-tier cold start can exceed a minute; retry budget must cover it.
HEALTH_WAIT_S = 180.0
HEALTH_REQUEST_TIMEOUT_S = 30.0
CLIP_BODY = b"netrapi-sprint-e\n"

INTEGRATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = INTEGRATION_DIR.parents[2]
MAIN_DIR = REPO_ROOT / "src" / "main"
BACKEND_DIR = MAIN_DIR / "backend"
EDGE_DIR = MAIN_DIR / "edge"
DB_DIR = MAIN_DIR / "db"
ALEMBIC_INI = DB_DIR / "alembic.ini"


def configure_import_path() -> None:
    for entry in (str(MAIN_DIR), str(EDGE_DIR), str(BACKEND_DIR), str(INTEGRATION_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def api_origin() -> str:
    raw = (os.environ.get("NETRAPI_API_URL") or DEFAULT_ORIGIN).strip().rstrip("/")
    if not raw:
        raise RuntimeError("NETRAPI_API_URL is empty")
    return raw


def apply_edge_ingest_auth(origin: str | None = None) -> str:
    """Load ``src/main/edge/.env`` and bind CloudIngest auth. Returns origin.

    Does not read ``src/main/backend/.env`` — Render already holds those secrets.
    """
    from netrapi.backend_auth import apply_edge_env, clear_ingest_auth, load_ingest_auth

    apply_edge_env()
    clear_ingest_auth()
    resolved = (origin or api_origin()).strip().rstrip("/")
    if not resolved:
        raise RuntimeError("NETRAPI_API_URL is empty")
    key = (os.environ.get("NETRAPI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "NETRAPI_API_KEY not set. Put it in src/main/edge/.env "
            "(same key Render uses)."
        )
    os.environ["NETRAPI_API_URL"] = resolved
    os.environ["NETRAPI_API_KEY"] = key
    load_ingest_auth()
    return resolved


def load_backend_settings():
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
        return settings
    finally:
        if saved_url is not None:
            os.environ["DATABASE_URL"] = saved_url
        if saved_key is not None:
            os.environ["NETRAPI_API_KEY"] = saved_key
        get_settings.cache_clear()


def wait_health(origin: str, *, timeout_s: float = HEALTH_WAIT_S) -> dict:
    deadline = time.monotonic() + timeout_s
    url = f"{origin}/health"
    last = "no attempt"
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=HEALTH_REQUEST_TIMEOUT_S) as response:
                if getattr(response, "status", 200) != 200:
                    last = f"HTTP {response.status}"
                    time.sleep(2)
                    continue
                body = json.loads(response.read().decode("utf-8"))
                if body.get("status") != "ok":
                    last = f"unexpected body {body!r}"
                    time.sleep(2)
                    continue
                raw_time = body.get("time")
                if not isinstance(raw_time, str) or not raw_time:
                    last = f"missing time {body!r}"
                    time.sleep(2)
                    continue
                datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                return body
        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            OSError,
            json.JSONDecodeError,
        ) as exc:
            # Py3.9: socket.timeout is not TimeoutError; bare timeouts must retry
            # through Render cold start instead of aborting the wait loop.
            last = str(exc)
            time.sleep(2)
    raise RuntimeError(f"GET {url} did not succeed within {timeout_s:.0f}s: {last}")


def http_json(origin: str, method: str, path: str, *, headers=None, body=None, timeout=30.0):
    import httpx

    with httpx.Client(base_url=origin, timeout=timeout) as client:
        response = client.request(method, path, headers=headers, json=body)
    return response


def s3_client(settings):
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


def init_sqlite(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    from db.database import init_engine, set_database_url_override

    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")
    set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    init_engine(url)


def seed_local_event(*, run_id: int, clip_path: Path, include_trip: bool = True) -> dict[str, int]:
    from netrapi.local_store import LocalStore

    started = datetime.now(timezone.utc).replace(microsecond=0)
    store = LocalStore()
    session_id = store.start_session(start_time=started, row_id=run_id)
    segment_id = None
    if include_trip:
        segment_id = store.persist_trip_segment(
            driving_session_id=session_id,
            local_path=clip_path,
            start_time=started,
            end_time=started + timedelta(seconds=30),
            order_number=1,
            row_id=run_id,
        )
    event_id = store.persist_event(
        driving_session_id=session_id,
        time=started + timedelta(seconds=12),
        type_value="rolling-stop",
        clip_path=clip_path,
        fps=30,
        order_number=1,
        num_frames=60,
        clip_start=started,
        clip_end=started + timedelta(seconds=2),
        event_id=run_id,
        clip_id=run_id,
        knn_stage1=(0.4, 0.12, 0.9, 0.08),
        knn_stage2=(0.12, 4.2),
        approach={
            "peak_area_pct": 1.1,
            "approach_duration_s": 1.8,
            "increasing_fraction": 0.7,
            "log_linear_r2": 0.85,
            "drop_duration_s": 0.4,
            "post_drop_holds": False,
            "fail_reasons": (),
        },
        trip_segment_id=segment_id,
        trip_offset_seconds=12.0 if segment_id is not None else None,
    )
    exception_id = store.persist_exception(
        driving_session_id=session_id,
        message=f"sprint-e sample operational exception {run_id}",
        time=started,
        is_fatal=False,
        row_id=run_id,
    )
    ids = {
        "session_id": session_id,
        "event_id": event_id,
        "clip_id": run_id,
        "exception_id": exception_id,
    }
    if segment_id is not None:
        ids["segment_id"] = segment_id
    return ids


def bind_edge_to_origin(origin: str, api_key: str) -> None:
    from netrapi.backend_auth import clear_ingest_auth, load_ingest_auth

    os.environ["NETRAPI_API_URL"] = origin
    os.environ["NETRAPI_API_KEY"] = api_key
    clear_ingest_auth()
    load_ingest_auth()


def inspect_uploaded_event(
    settings,
    *,
    session_id: int,
    event_id: int,
    clip_id: int,
    segment_id: int | None = None,
    exception_id: int | None = None,
    local_clip_key: str | None = None,
    local_trip_key: str | None = None,
    body_len: int | None = None,
    require_knn: bool = True,
) -> tuple[str, str | None]:
    from sqlmodel import Session, create_engine, select

    from db.models import (
        ApproachParameters,
        AutoClassification,
        Classification,
        Clip,
        DrivingSession,
        Event,
        EventTripLocation,
        KnnParameter,
        OperationalException,
        TripSegment,
    )

    object_key = None
    trip_key = None
    pg = create_engine(settings.database_url)
    try:
        with Session(pg) as cloud:
            cloud_event = cloud.get(Event, event_id)
            if cloud_event is None:
                raise RuntimeError(f"Postgres missing event {event_id}")
            cloud_clip = cloud.exec(select(Clip).where(Clip.event_id == event_id)).first()
            if cloud_clip is None:
                raise RuntimeError("Postgres clip missing")
            if cloud_clip.s3_stored is not True or not cloud_clip.s3_key:
                raise RuntimeError(
                    f"Postgres s3 flags {cloud_clip.s3_key!r} {cloud_clip.s3_stored!r}"
                )
            if local_clip_key is not None and cloud_clip.s3_key != local_clip_key:
                raise RuntimeError(
                    f"sqlite/postgres s3_key mismatch: {local_clip_key!r} vs "
                    f"{cloud_clip.s3_key!r}"
                )
            if body_len is not None and cloud_clip.file_size_bytes != body_len:
                raise RuntimeError(
                    f"Postgres file_size_bytes {cloud_clip.file_size_bytes!r}"
                )
            if cloud_clip.id != clip_id:
                raise RuntimeError(f"Postgres clip id {cloud_clip.id!r} != {clip_id}")
            object_key = cloud_clip.s3_key
            classification = cloud.exec(
                select(Classification).where(
                    Classification.event_id == event_id,
                    Classification.kind == "auto",
                )
            ).first()
            if classification is None:
                raise RuntimeError("Postgres auto classification missing")
            auto = cloud.exec(
                select(AutoClassification).where(
                    AutoClassification.classification_id == classification.id
                )
            ).first()
            if auto is None:
                raise RuntimeError("Postgres auto_classification missing")
            if require_knn:
                knn_rows = cloud.exec(
                    select(KnnParameter).where(
                        KnnParameter.auto_classification_id == auto.id
                    )
                ).all()
                if len(knn_rows) != 6:
                    raise RuntimeError(f"Postgres knn_parameter count {len(knn_rows)}")
                approach = cloud.exec(
                    select(ApproachParameters).where(
                        ApproachParameters.auto_classification_id == auto.id
                    )
                ).first()
                if approach is None:
                    raise RuntimeError("Postgres approach_parameters missing")
            if segment_id is not None:
                loc = cloud.exec(
                    select(EventTripLocation).where(EventTripLocation.event_id == event_id)
                ).first()
                if loc is None or loc.trip_segment_id != segment_id:
                    raise RuntimeError("Postgres event_trip_location missing")
                cloud_trip = cloud.get(TripSegment, segment_id)
                if cloud_trip is None:
                    raise RuntimeError("Postgres trip_segment missing")
                if cloud_trip.s3_stored is not True or not cloud_trip.s3_key:
                    raise RuntimeError(
                        f"Postgres trip s3 flags {cloud_trip.s3_key!r} "
                        f"{cloud_trip.s3_stored!r}"
                    )
                if local_trip_key is not None and cloud_trip.s3_key != local_trip_key:
                    raise RuntimeError(
                        f"sqlite/postgres trip s3_key mismatch: "
                        f"{local_trip_key!r} vs {cloud_trip.s3_key!r}"
                    )
                trip_key = cloud_trip.s3_key
            if cloud.get(DrivingSession, session_id) is None:
                raise RuntimeError("Postgres driving_session missing")
            if exception_id is not None and cloud.get(OperationalException, exception_id) is None:
                raise RuntimeError("Postgres operational_exception missing")
    finally:
        pg.dispose()

    s3, bucket = s3_client(settings)
    head = s3.head_object(Bucket=bucket, Key=object_key)
    if body_len is not None and head.get("ContentLength") != body_len:
        raise RuntimeError(f"S3 content_length {head.get('ContentLength')!r}")
    if trip_key:
        trip_head = s3.head_object(Bucket=bucket, Key=trip_key)
        if body_len is not None and trip_head.get("ContentLength") != body_len:
            raise RuntimeError(
                f"S3 trip content_length {trip_head.get('ContentLength')!r}"
            )
    return object_key, trip_key


def driving_event_payload(run_id: int, start: datetime | None = None) -> dict:
    started = start or datetime(2026, 8, 22, 18, 0, 0, tzinfo=timezone.utc)
    return {
        "id": run_id,
        "driving_session_id": run_id,
        "time": iso_z(started),
        "clip": {
            "id": run_id,
            "fps": 30,
            "order_number": 1,
            "num_frames": 60,
            "start_time": iso_z(started),
            "end_time": iso_z(started),
            "init_local_stored": True,
        },
        "auto_classification": {
            "kind": "auto",
            "classification_type_id": 2,
            "stage1_classification_type_id": 4,
            "stage2_classification_type_id": 2,
        },
    }
