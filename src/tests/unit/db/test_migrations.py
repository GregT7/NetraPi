from __future__ import annotations

from pathlib import Path

from sqlmodel import select

import db.database as database
from db.database import get_session, init_engine
from db.models import ClassificationType, MasterConfig

ALEMBIC_INI = Path(__file__).resolve().parents[3] / "main" / "db" / "alembic.ini"


def _upgrade(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    database.set_database_url_override(url)
    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def test_alembic_ini_exists() -> None:
    assert ALEMBIC_INI.is_file()


def test_upgrade_head_seeds_master_config_and_types(sqlite_url: str) -> None:
    _upgrade(sqlite_url)
    init_engine(sqlite_url)
    with get_session() as session:
        master = session.get(MasterConfig, 1)
        assert master is not None
        assert master.id == 1
        values = {row.value for row in session.exec(select(ClassificationType)).all()}
    assert "complete-stop" in values
    assert "rolling-stop" in values
    assert "run-through" in values
