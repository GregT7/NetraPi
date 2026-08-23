from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, select

import db.database as database
import db.models  # noqa: F401
from db.database import get_session, init_engine
from db.models import DrivingSession, MasterConfig


def test_init_engine_none_uses_load_database_url(
    sqlite_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(database, "load_database_url", lambda: sqlite_url)
    engine = init_engine()
    assert str(engine.url) == sqlite_url
    assert database._engine is engine


def test_load_database_url_raises_when_env_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(database, "ENV_PATH", tmp_path / "missing.env")
    database.set_database_url_override(None)
    with pytest.raises(database.DatabaseUrlError, match="DATABASE_URL is not set"):
        database.load_database_url()


def test_load_database_url_reads_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=sqlite:///from-env.db\n", encoding="utf-8")
    monkeypatch.setattr(database, "ENV_PATH", env_path)
    monkeypatch.setattr(database, "_PACKAGE_DIR", tmp_path)
    database.set_database_url_override(None)
    url = database.load_database_url()
    assert url.endswith("from-env.db")
    assert "from-env.db" in url


def test_load_database_url_override_wins_over_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=sqlite:///from-env.db\n", encoding="utf-8")
    monkeypatch.setattr(database, "ENV_PATH", env_path)
    database.set_database_url_override(f"sqlite:///{(tmp_path / 'override.db').as_posix()}")
    try:
        url = database.load_database_url()
        assert url.endswith("override.db")
    finally:
        database.set_database_url_override(None)


def test_load_database_url_ignores_process_env_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=sqlite:///from-env.db\n", encoding="utf-8")
    monkeypatch.setattr(database, "ENV_PATH", env_path)
    monkeypatch.setattr(database, "_PACKAGE_DIR", tmp_path)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://netrapi:netrapi@postgres:5432/netrapi",
    )
    database.set_database_url_override(None)
    url = database.load_database_url()
    assert url.endswith("from-env.db")


def test_load_database_url_process_env_wins_over_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=sqlite:///from-env.db\n", encoding="utf-8")
    monkeypatch.setattr(database, "ENV_PATH", env_path)
    postgres = "postgresql+psycopg2://netrapi:netrapi@postgres:5432/netrapi"
    monkeypatch.setenv("DATABASE_URL", postgres)
    database.set_database_url_override(None)
    assert database.load_database_url(from_process_env=True) == postgres


def test_load_database_url_override_wins_over_process_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=sqlite:///from-env.db\n", encoding="utf-8")
    monkeypatch.setattr(database, "ENV_PATH", env_path)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://netrapi:netrapi@postgres:5432/netrapi",
    )
    database.set_database_url_override(f"sqlite:///{(tmp_path / 'override.db').as_posix()}")
    try:
        url = database.load_database_url(from_process_env=True)
        assert url.endswith("override.db")
    finally:
        database.set_database_url_override(None)


def test_resolve_sqlite_url_relative_uses_package_dir() -> None:
    url = database.resolve_sqlite_url("sqlite:///netrapi.db")
    assert url == f"sqlite:///{(database._PACKAGE_DIR / 'netrapi.db').resolve().as_posix()}"


def test_init_engine_sqlite_sets_check_same_thread() -> None:
    with (
        patch("db.database.event.listens_for"),
        patch("db.database.create_engine", return_value=MagicMock()) as create,
    ):
        init_engine("sqlite:///:memory:")
    create.assert_called_once_with(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )


def test_init_engine_postgres_has_no_sqlite_connect_args() -> None:
    url = "postgresql+psycopg2://netrapi:netrapi@postgres:5432/netrapi"
    with patch("db.database.create_engine", return_value=MagicMock()) as create:
        init_engine(url)
    create.assert_called_once_with(url)


def test_get_session_uses_initialized_engine(sqlite_url: str) -> None:
    engine = init_engine(sqlite_url)
    session = get_session()
    try:
        assert session.get_bind() is engine
    finally:
        session.close()


def test_sqlite_foreign_keys_reject_orphan_session(sqlite_url: str) -> None:
    engine = init_engine(sqlite_url)
    SQLModel.metadata.create_all(engine)
    with get_session() as session:
        session.add(
            DrivingSession(
                master_config_id=99,
                start_time=datetime(2026, 8, 20, tzinfo=timezone.utc),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_sqlite_session_round_trip(sqlite_url: str) -> None:
    engine = init_engine(sqlite_url)
    SQLModel.metadata.create_all(engine)
    started = datetime(2026, 8, 20, 12, 0, 0)
    with get_session() as session:
        session.add(MasterConfig(name="unit", created_at=started, note=""))
        session.commit()
        session.add(DrivingSession(master_config_id=1, start_time=started))
        session.commit()
    with get_session() as session:
        row = session.exec(select(DrivingSession)).one()
        assert row.master_config_id == 1
        assert row.start_time == started
