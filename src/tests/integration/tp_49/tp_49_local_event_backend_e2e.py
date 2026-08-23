"""
TP-49: Local end-to-end event persistence via backend (system).

Writes one event to SQLite + a small clip file, then uses CloudIngest
(the same client the capture loop calls) against a live FastAPI process
pointed at Supabase. Client PUT uses only the presigned URL (no AWS keys
on the "edge" side).

Usage (from repo root, venv with fastapi + boto3 + alembic + psycopg2):

    python src/tests/integration/tp_49/tp_49_local_event_backend_e2e.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
MAIN_DIR = REPO_ROOT / "src" / "main"
BACKEND_DIR = MAIN_DIR / "backend"
EDGE_DIR = MAIN_DIR / "edge"
DB_DIR = MAIN_DIR / "db"
ALEMBIC_INI = DB_DIR / "alembic.ini"
OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"
CLIP_PATH = SCRIPT_DIR / "clip.mp4"
BODY = b"netrapi-tp-49\n"
HEALTH_WAIT_S = 30.0


def _configure_import_path() -> None:
    for entry in (str(MAIN_DIR), str(EDGE_DIR), str(BACKEND_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_health(base: str) -> None:
    deadline = time.monotonic() + HEALTH_WAIT_S
    url = f"{base}/health"
    last = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if getattr(response, "status", 200) == 200:
                    return
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(0.4)
    raise RuntimeError(f"FastAPI /health did not become ready: {last}")


def _init_sqlite(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    from db.database import init_engine, set_database_url_override

    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")
    set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    init_engine(url)


def _backend_settings():
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
        else:
            os.environ.pop("DATABASE_URL", None)
        if saved_key is not None:
            os.environ["NETRAPI_API_KEY"] = saved_key
        get_settings.cache_clear()


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
    print("TP-49: Local event -> FastAPI -> S3 + Postgres", flush=True)
    print("  1. SQLite session + event + clip file + trip segment", flush=True)
    print("  2. CloudIngest against live FastAPI (Supabase URI)", flush=True)
    print("  3. Inspect Postgres rows and S3 clip + trip objects", flush=True)

    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()
    CLIP_PATH.write_bytes(BODY)

    sqlite_url = _sqlite_url(OUTPUT_DB_PATH)
    settings = _backend_settings()
    api_key = settings.netrapi_api_key
    os.environ["DATABASE_URL"] = sqlite_url
    os.environ["NETRAPI_API_KEY"] = api_key
    port = _free_port()
    api_url = f"http://127.0.0.1:{port}"
    os.environ["NETRAPI_API_URL"] = api_url

    from netrapi.backend_auth import clear_ingest_auth, load_ingest_auth

    clear_ingest_auth()
    load_ingest_auth()

    child_env = os.environ.copy()
    child_env["DATABASE_URL"] = settings.database_url
    child_env["NETRAPI_API_KEY"] = api_key
    child_env["PYTHONPATH"] = os.pathsep.join(
        [str(MAIN_DIR), str(BACKEND_DIR), child_env.get("PYTHONPATH", "")]
    )
    log_path = SCRIPT_DIR / "uvicorn.stderr.log"
    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            str(BACKEND_DIR),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(BACKEND_DIR),
        env=child_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    object_key = None
    trip_key = None
    s3 = None
    bucket = None
    passed = False
    try:
        _wait_health(api_url)
        _init_sqlite(sqlite_url)

        from sqlmodel import Session, create_engine, select

        from db.database import get_session
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
        from netrapi.cloud_ingest import CloudIngest
        from netrapi.local_store import LocalStore

        started = datetime.now(timezone.utc).replace(microsecond=0)
        run_id = 49_000_000 + int(time.time()) % 900_000
        store = LocalStore()
        session_id = store.start_session(start_time=started, row_id=run_id)
        segment_id = store.persist_trip_segment(
            driving_session_id=session_id,
            local_path=CLIP_PATH,
            start_time=started,
            end_time=started + timedelta(seconds=30),
            order_number=1,
            row_id=run_id,
        )
        event_id = store.persist_event(
            driving_session_id=session_id,
            time=started + timedelta(seconds=12),
            type_value="rolling-stop",
            clip_path=CLIP_PATH,
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
            trip_offset_seconds=12.0,
        )
        clip_id = run_id
        exception_id = store.persist_exception(
            driving_session_id=session_id,
            message="tp-49 sample operational exception",
            time=started,
            is_fatal=False,
            row_id=run_id,
        )

        ingest = CloudIngest()
        ingest.sync_session(session_id)
        ingest.sync_trip_segment(segment_id)
        ingest.sync_event(event_id)
        ingest.drain_trip_segments()
        ingest.sync_operational_exception(exception_id)

        with get_session() as local:
            local_clip = local.get(Clip, clip_id)
            if local_clip is None:
                raise RuntimeError("SQLite clip missing after ingest")
            if local_clip.s3_stored is not True or not local_clip.s3_key:
                raise RuntimeError(
                    f"SQLite s3 flags {local_clip.s3_key!r} {local_clip.s3_stored!r}"
                )
            if local_clip.file_size_bytes != len(BODY):
                raise RuntimeError(
                    f"SQLite file_size_bytes {local_clip.file_size_bytes!r}"
                )
            local_key = local_clip.s3_key
            local_trip = local.get(TripSegment, segment_id)
            if local_trip is None:
                raise RuntimeError("SQLite trip_segment missing after drain")
            if local_trip.s3_stored is not True or not local_trip.s3_key:
                raise RuntimeError(
                    f"SQLite trip s3 flags {local_trip.s3_key!r} "
                    f"{local_trip.s3_stored!r}"
                )
            if local_trip.file_size_bytes != len(BODY):
                raise RuntimeError(
                    f"SQLite trip file_size_bytes {local_trip.file_size_bytes!r}"
                )
            local_trip_key = local_trip.s3_key

        pg = create_engine(settings.database_url)
        try:
            with Session(pg) as cloud:
                cloud_event = cloud.get(Event, event_id)
                if cloud_event is None:
                    raise RuntimeError(f"Postgres missing event {event_id}")
                if cloud_event.driving_session_id != session_id:
                    raise RuntimeError("Postgres driving_session_id mismatch")
                cloud_clip = cloud.exec(
                    select(Clip).where(Clip.event_id == event_id)
                ).first()
                if cloud_clip is None:
                    raise RuntimeError("Postgres clip missing")
                if cloud_clip.s3_stored is not True or not cloud_clip.s3_key:
                    raise RuntimeError(
                        f"Postgres s3 flags {cloud_clip.s3_key!r} "
                        f"{cloud_clip.s3_stored!r}"
                    )
                if cloud_clip.s3_key != local_key:
                    raise RuntimeError(
                        f"sqlite/postgres s3_key mismatch: {local_key!r} vs "
                        f"{cloud_clip.s3_key!r}"
                    )
                if cloud_clip.file_size_bytes != len(BODY):
                    raise RuntimeError(
                        f"Postgres file_size_bytes {cloud_clip.file_size_bytes!r}"
                    )
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
                loc = cloud.exec(
                    select(EventTripLocation).where(
                        EventTripLocation.event_id == event_id
                    )
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
                if cloud_trip.s3_key != local_trip_key:
                    raise RuntimeError(
                        f"sqlite/postgres trip s3_key mismatch: "
                        f"{local_trip_key!r} vs {cloud_trip.s3_key!r}"
                    )
                if cloud_trip.file_size_bytes != len(BODY):
                    raise RuntimeError(
                        f"Postgres trip file_size_bytes {cloud_trip.file_size_bytes!r}"
                    )
                trip_key = cloud_trip.s3_key
                if cloud.get(DrivingSession, session_id) is None:
                    raise RuntimeError("Postgres driving_session missing")
                if cloud.get(OperationalException, exception_id) is None:
                    raise RuntimeError("Postgres operational_exception missing")
        finally:
            pg.dispose()

        s3, bucket = _s3_client(settings)
        head = s3.head_object(Bucket=bucket, Key=object_key)
        if head.get("ContentLength") != len(BODY):
            raise RuntimeError(
                f"S3 content_length {head.get('ContentLength')!r}"
            )
        trip_head = s3.head_object(Bucket=bucket, Key=trip_key)
        if trip_head.get("ContentLength") != len(BODY):
            raise RuntimeError(
                f"S3 trip content_length {trip_head.get('ContentLength')!r}"
            )
        print(
            f"  sqlite/postgres event {event_id} clip {clip_id} -> {object_key}",
            flush=True,
        )
        print(
            f"  sqlite/postgres trip_segment {segment_id} -> {trip_key}",
            flush=True,
        )
        passed = True
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        try:
            log_file.flush()
            print(log_path.read_text(encoding="utf-8")[-2000:], file=sys.stderr)
        except Exception:
            pass
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        try:
            log_file.close()
        except Exception:
            pass
        if not passed and s3 is not None and bucket:
            for key in (object_key, trip_key):
                if not key:
                    continue
                try:
                    s3.delete_object(Bucket=bucket, Key=key)
                except Exception:
                    pass
        from netrapi.backend_auth import clear_ingest_auth as _clear

        _clear()

    print("PASS: local SQLite event uploaded via backend to S3 + Postgres")
    print(f"  inspect sqlite: {OUTPUT_DB_PATH}")
    print(f"  inspect S3 clip (left in bucket): {object_key}")
    print(f"  inspect S3 trip (left in bucket): {trip_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
