"""
TP-53: Unsafe event to cloud via deployed backend (system).

Harness: LocalStore SQLite event + clip, then CloudIngest against Render
(the same client the capture loop uses). Confirms upload via local SQLite
``s3_stored`` / ``s3_key`` after Render confirm. Loads only
``src/main/edge/.env``. In-car buzzer + live detection is the optional
demo path in the README.

Usage (from repo root, Pi edge venv with alembic):

    python src/tests/integration/tp_53/tp_53_unsafe_event_deployed_backend.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import (  # noqa: E402
    CLIP_BODY,
    apply_edge_ingest_auth,
    configure_import_path,
    init_sqlite,
    seed_local_event,
    sqlite_url,
    wait_health,
)

OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"
CLIP_PATH = SCRIPT_DIR / "clip.mp4"


def main() -> int:
    configure_import_path()
    print("TP-53: Unsafe event to cloud via deployed backend", flush=True)
    print("  1. SQLite session + rolling-stop event + clip + trip", flush=True)
    print("  2. CloudIngest against Render (no local uvicorn)", flush=True)
    print("  3. Confirm local SQLite s3 flags", flush=True)

    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()
    CLIP_PATH.write_bytes(CLIP_BODY)

    object_key = None
    trip_key = None
    try:
        origin = apply_edge_ingest_auth()
        print(f"  origin: {origin}", flush=True)
        wait_health(origin)

        sqlite = sqlite_url(OUTPUT_DB_PATH)
        os.environ["DATABASE_URL"] = sqlite
        init_sqlite(sqlite)

        from db.database import get_session
        from db.models import Clip, TripSegment
        from netrapi.backend_auth import clear_ingest_auth
        from netrapi.cloud_ingest import CloudIngest

        run_id = 53_000_000 + int(time.time()) % 900_000
        ids = seed_local_event(run_id=run_id, clip_path=CLIP_PATH, include_trip=True)
        ingest = CloudIngest()
        ingest.sync_session(ids["session_id"])
        ingest.sync_trip_segment(ids["segment_id"])
        ingest.sync_event(ids["event_id"])
        ingest.drain_trip_segments()
        ingest.sync_operational_exception(ids["exception_id"])

        with get_session() as local:
            local_clip = local.get(Clip, ids["clip_id"])
            if local_clip is None or local_clip.s3_stored is not True or not local_clip.s3_key:
                raise RuntimeError(f"SQLite clip s3 flags {local_clip!r}")
            if local_clip.file_size_bytes != len(CLIP_BODY):
                raise RuntimeError(f"SQLite file_size_bytes {local_clip.file_size_bytes!r}")
            local_trip = local.get(TripSegment, ids["segment_id"])
            if local_trip is None or local_trip.s3_stored is not True or not local_trip.s3_key:
                raise RuntimeError(f"SQLite trip s3 flags {local_trip!r}")
            object_key = local_clip.s3_key
            trip_key = local_trip.s3_key

        print(
            f"  sqlite event {ids['event_id']} clip {ids['clip_id']} -> {object_key}",
            flush=True,
        )
        print(
            f"  sqlite trip_segment {ids['segment_id']} -> {trip_key}",
            flush=True,
        )
        clear_ingest_auth()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: local SQLite event uploaded via Render (s3 confirm)")
    print(f"  inspect sqlite: {OUTPUT_DB_PATH}")
    print(f"  clip s3_key: {object_key}")
    print(f"  trip s3_key: {trip_key}")
    print("  optional Postgres/S3 console: see AT-7.1 README")
    print("  in-car buzzer/detection: see README (optional demo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
