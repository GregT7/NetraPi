"""
TP-56: Deployed system smoke (system).

Minimal Render path: GET /health, one LocalStore event, CloudIngest,
then confirm via local SQLite s3 flags. No frontend. Loads only
``src/main/edge/.env`` (not backend ``.env``).

Usage (from repo root, Pi edge venv with alembic):

    python src/tests/integration/tp_56/tp_56_deployed_system_smoke.py
"""

from __future__ import annotations

import json
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
    print("TP-56: Deployed system smoke", flush=True)
    print("  1. GET /health", flush=True)
    print("  2. One SQLite event -> CloudIngest -> Render", flush=True)
    print("  3. Confirm local SQLite s3 flags (no frontend)", flush=True)

    if OUTPUT_DB_PATH.exists():
        OUTPUT_DB_PATH.unlink()
    CLIP_PATH.write_bytes(CLIP_BODY)

    try:
        origin = apply_edge_ingest_auth()
        print(f"  origin: {origin}", flush=True)

        sqlite = sqlite_url(OUTPUT_DB_PATH)
        os.environ["DATABASE_URL"] = sqlite

        body = wait_health(origin)
        print(json.dumps(body, indent=2), flush=True)
        init_sqlite(sqlite)

        from db.database import get_session
        from db.models import Clip
        from netrapi.backend_auth import clear_ingest_auth
        from netrapi.cloud_ingest import CloudIngest

        run_id = 56_000_000 + int(time.time()) % 900_000
        ids = seed_local_event(run_id=run_id, clip_path=CLIP_PATH, include_trip=False)
        ingest = CloudIngest()
        ingest.sync_session(ids["session_id"])
        ingest.sync_event(ids["event_id"])
        ingest.sync_operational_exception(ids["exception_id"])

        with get_session() as local:
            local_clip = local.get(Clip, ids["clip_id"])
            if local_clip is None or local_clip.s3_stored is not True:
                raise RuntimeError("local clip not confirmed after CloudIngest")
            if not local_clip.s3_key:
                raise RuntimeError("local clip missing s3_key after CloudIngest")
            object_key = local_clip.s3_key

        clear_ingest_auth()
        print(f"  smoke event {ids['event_id']} -> {object_key}", flush=True)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: deployed smoke completed via API (local s3 confirm)")
    print(f"  inspect sqlite: {OUTPUT_DB_PATH}")
    print("  optional Postgres/S3: see AT-7.1 README")
    print("  in-car buzzer: optional; see TP-53 README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
