"""
TP-55: Restart recovery then upload (system).

Writes a local SQLite event + clip, disposes the engine (simulated edge
restart), confirms the rows are still there, then CloudIngest against
Render. Loads only ``src/main/edge/.env``. Confirms upload via local
SQLite ``s3_stored`` / ``s3_key``.

Usage (from repo root, Pi edge venv with alembic):

    python src/tests/integration/tp_55/tp_55_restart_recovery_upload.py
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


def _dispose_engine() -> None:
    from db import database as db_mod

    db_mod.set_database_url_override(None)
    if db_mod._engine is not None:
        db_mod._engine.dispose()
        db_mod._engine = None


def main() -> int:
    configure_import_path()
    print("TP-55: Restart recovery then upload", flush=True)
    print("  1. Local SQLite event + clip (no upload yet)", flush=True)
    print("  2. Dispose engine (simulated restart)", flush=True)
    print("  3. Re-open SQLite, then CloudIngest against Render", flush=True)

    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()
    CLIP_PATH.write_bytes(CLIP_BODY)

    try:
        origin = apply_edge_ingest_auth()
        print(f"  origin: {origin}", flush=True)
        wait_health(origin)

        sqlite = sqlite_url(OUTPUT_DB_PATH)
        os.environ["DATABASE_URL"] = sqlite
        init_sqlite(sqlite)

        from db.database import get_session
        from db.models import Clip, Event
        from netrapi.backend_auth import clear_ingest_auth
        from netrapi.cloud_ingest import CloudIngest

        run_id = 55_000_000 + int(time.time()) % 900_000
        ids = seed_local_event(run_id=run_id, clip_path=CLIP_PATH, include_trip=False)
        with get_session() as local:
            if local.get(Event, ids["event_id"]) is None:
                raise RuntimeError("event missing before restart")
            before = local.get(Clip, ids["clip_id"])
            if before is None or not CLIP_PATH.is_file():
                raise RuntimeError("clip missing before restart")
            if before.s3_stored is True:
                raise RuntimeError("clip already marked uploaded before restart")

        _dispose_engine()
        init_sqlite(sqlite)

        with get_session() as local:
            after_event = local.get(Event, ids["event_id"])
            after_clip = local.get(Clip, ids["clip_id"])
            if after_event is None or after_clip is None:
                raise RuntimeError("local event/clip did not survive restart")
            if not CLIP_PATH.is_file():
                raise RuntimeError("clip file missing after restart")

        ingest = CloudIngest()
        ingest.sync_session(ids["session_id"])
        ingest.sync_event(ids["event_id"])
        ingest.sync_operational_exception(ids["exception_id"])

        with get_session() as local:
            local_clip = local.get(Clip, ids["clip_id"])
            if local_clip is None or local_clip.s3_stored is not True:
                raise RuntimeError("SQLite clip not confirmed after upload")
            if not local_clip.s3_key:
                raise RuntimeError("SQLite clip missing s3_key after upload")
            object_key = local_clip.s3_key

        clear_ingest_auth()
        print(f"  event {ids['event_id']} survived restart -> {object_key}", flush=True)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: local data survived restart and uploaded via Render")
    print(f"  inspect sqlite: {OUTPUT_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
