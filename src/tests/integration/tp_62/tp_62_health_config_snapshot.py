"""
TP-62: Health settings snapshot (integration).

Alembic head seeds health_config on master_config id 1. Unchanged
health.json reuses that snapshot. Changing a health timeout inserts a
new master_config + health_config row.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from sqlmodel import select

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import configure_import_path, init_sqlite, sqlite_url  # noqa: E402

configure_import_path()


def _reset_engine() -> None:
    import db.database as database

    database.set_database_url_override(None)
    if database._engine is not None:
        database._engine.dispose()
        database._engine = None


def main() -> int:
    from db.config_snapshot import (
        edge_json_config_dir,
        ensure_snapshot_from_json_dir,
        find_or_create_snapshot,
        fingerprint,
        payload_from_db,
        payload_from_json_dir,
    )
    from db.database import get_session, init_engine
    from db.models import HealthConfig, MasterConfig

    print("TP-62: Health settings snapshot", flush=True)
    tmp_dir = SCRIPT_DIR / "_tmp"
    tmp_dir.mkdir(exist_ok=True)
    db_path = tmp_dir / "netrapi.db"
    url = sqlite_url(db_path)
    try:
        print("  1. Alembic upgrade head seeds health_config on id 1", flush=True)
        init_sqlite(url)
        init_engine(url)
        json_payload = payload_from_json_dir(edge_json_config_dir())
        with get_session() as session:
            db_payload = payload_from_db(session, 1)
            master_id, created = find_or_create_snapshot(session, json_payload)
            session.commit()
            health = session.exec(
                select(HealthConfig).where(HealthConfig.master_config_id == 1)
            ).one()
            count = len(session.exec(select(MasterConfig)).all())
        if fingerprint(json_payload) != fingerprint(db_payload):
            raise RuntimeError("live JSON fingerprint should match seeded snapshot")
        if (master_id, created) != (1, False) or count != 1:
            raise RuntimeError(
                f"unchanged JSON should reuse id 1, got {(master_id, created, count)}"
            )
        if health.render_wait_s != 90:
            raise RuntimeError(f"seeded render_wait_s should be 90, got {health.render_wait_s}")

        print("  2. Change health.json timeout => new snapshot", flush=True)
        config_dir = tmp_dir / "config"
        if config_dir.exists():
            shutil.rmtree(config_dir)
        shutil.copytree(edge_json_config_dir(), config_dir)
        health_path = config_dir / "health.json"
        health_json = json.loads(health_path.read_text(encoding="utf-8"))
        health_json["render_wait_s"] = 42
        health_path.write_text(json.dumps(health_json), encoding="utf-8")
        with get_session() as session:
            first_id, created = ensure_snapshot_from_json_dir(session, config_dir)
            session.commit()
            row = session.exec(
                select(HealthConfig).where(HealthConfig.master_config_id == first_id)
            ).one()
            count = len(session.exec(select(MasterConfig)).all())
        if not created or first_id == 1:
            raise RuntimeError("changed health.json should insert a new snapshot")
        if row.render_wait_s != 42 or count != 2:
            raise RuntimeError(
                f"new health_config render_wait_s=42, count=2; got {row.render_wait_s} {count}"
            )
        print("PASS: health_config seeded, fingerprint reuse, change inserts row", flush=True)
        return 0
    finally:
        _reset_engine()
        if tmp_dir.is_dir():
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _reset_engine()
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
