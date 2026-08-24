from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlmodel import select

from db.config_snapshot import (
    edge_json_config_dir,
    ensure_snapshot_from_json_dir,
    find_or_create_snapshot,
    fingerprint,
    payload_from_db,
    payload_from_json_dir,
)
from db.database import get_session, init_engine
from db.models import HealthConfig, KnnFeature, KnnParameter, MasterConfig, PreviewConfig
from db.writes import insert_driving_session, insert_local_event, knn_feature_ids

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "main" / "db" / "alembic.ini"


def _upgrade(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    import db.database as database

    database.set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def _copy_edge_json(tmp_path: Path) -> Path:
    dest = tmp_path / "config"
    shutil.copytree(edge_json_config_dir(), dest)
    return dest


def test_json_fingerprint_matches_seeded_snapshot(sqlite_url: str) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    json_payload = payload_from_json_dir(edge_json_config_dir())
    with get_session() as session:
        db_payload = payload_from_db(session, 1)
        master_id, created = find_or_create_snapshot(session, json_payload)
        session.commit()
        count = len(session.exec(select(MasterConfig)).all())
    assert fingerprint(json_payload) == fingerprint(db_payload)
    assert (master_id, created) == (1, False)
    assert count == 1


def test_changed_json_inserts_new_snapshot_and_second_call_reuses(
    sqlite_url: str, tmp_path: Path
) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    config_dir = _copy_edge_json(tmp_path)
    preview_path = config_dir / "preview.json"
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    preview["window_name"] = "Changed Preview"
    preview_path.write_text(json.dumps(preview), encoding="utf-8")
    with get_session() as session:
        first_id, created = ensure_snapshot_from_json_dir(session, config_dir)
        session.commit()
        second_id, created_again = ensure_snapshot_from_json_dir(session, config_dir)
        session.commit()
        preview_row = session.exec(
            select(PreviewConfig).where(PreviewConfig.master_config_id == first_id)
        ).one()
        count = len(session.exec(select(MasterConfig)).all())
    assert created is True
    assert first_id != 1
    assert (second_id, created_again) == (first_id, False)
    assert preview_row.window_name == "Changed Preview"
    assert count == 2


def test_changed_health_json_inserts_new_snapshot(
    sqlite_url: str, tmp_path: Path
) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    config_dir = _copy_edge_json(tmp_path)
    health_path = config_dir / "health.json"
    health = json.loads(health_path.read_text(encoding="utf-8"))
    health["render_wait_s"] = 42
    health_path.write_text(json.dumps(health), encoding="utf-8")
    with get_session() as session:
        first_id, created = ensure_snapshot_from_json_dir(session, config_dir)
        session.commit()
        row = session.exec(
            select(HealthConfig).where(HealthConfig.master_config_id == first_id)
        ).one()
        count = len(session.exec(select(MasterConfig)).all())
    assert created is True
    assert first_id != 1
    assert row.render_wait_s == 42
    assert count == 2


def test_knn_feature_ids_scoped_to_driving_session(
    sqlite_url: str, tmp_path: Path
) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    config_dir = _copy_edge_json(tmp_path)
    preview_path = config_dir / "preview.json"
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    preview["window_name"] = "Other Snapshot"
    preview_path.write_text(json.dumps(preview), encoding="utf-8")
    clip_path = tmp_path / "clip.mp4"
    clip_path.write_bytes(b"abcd")
    with get_session() as session:
        other_id, created = ensure_snapshot_from_json_dir(session, config_dir)
        session.commit()
        other_features = {
            row.id
            for row in session.exec(select(KnnFeature)).all()
            if row.knn_config_id != 1
        }
        driving = insert_driving_session(
            session, start_time=datetime(2026, 8, 22, 16, 0, 0)
        )
        scoped = knn_feature_ids(session, driving_session_id=driving.id)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=driving.start_time,
            type_value="rolling-stop",
            clip_path=clip_path,
            fps=30,
            order_number=1,
            num_frames=30,
            clip_start=driving.start_time,
            clip_end=driving.start_time,
            knn_stage1=(0.1, 0.2, 0.3, 0.4),
            knn_stage2=(0.2, 1.5),
        )
        event_id = event.id
        session.commit()
        used = {row.knn_feature_id for row in session.exec(select(KnnParameter)).all()}
    assert created is True
    assert other_id != 1
    assert set(scoped.values()) == {1, 2, 3, 4, 5, 6}
    assert used == {1, 2, 3, 4, 5, 6}
    assert used.isdisjoint(other_features)
    assert event_id is not None
