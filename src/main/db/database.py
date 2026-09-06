from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

_PACKAGE_DIR = Path(__file__).resolve().parent
_EDGE_DIR = _PACKAGE_DIR.parent / "edge"
ENV_PATH = _EDGE_DIR / ".env"
ALEMBIC_INI = _PACKAGE_DIR / "alembic.ini"

_engine: Engine | None = None
_url_override: str | None = None


class DatabaseUrlError(RuntimeError):
    """Raised when DATABASE_URL cannot be loaded from override, process env, or edge/.env."""


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def resolve_sqlite_url(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix) or url.startswith("sqlite:///:memory:"):
        return url
    rest = url[len(prefix) :]
    path = Path(rest)
    if not path.is_absolute():
        path = (_PACKAGE_DIR / path).resolve()
    else:
        path = path.resolve()
    return f"sqlite:///{path.as_posix()}"


def set_database_url_override(url: str | None) -> None:
    global _url_override
    _url_override = url


def load_database_url(*, from_process_env: bool = False) -> str:
    if _url_override:
        return resolve_sqlite_url(_url_override)
    if from_process_env:
        raw = (os.environ.get("DATABASE_URL") or "").strip()
        if raw:
            return resolve_sqlite_url(raw)
    if ENV_PATH.is_file():
        raw = _parse_env_file(ENV_PATH).get("DATABASE_URL", "").strip()
        if raw:
            return resolve_sqlite_url(raw)
    raise DatabaseUrlError(
        "DATABASE_URL is not set. Create src/main/edge/.env with "
        "DATABASE_URL=sqlite:///netrapi.db for Pi/SQLite, or set process "
        "DATABASE_URL for Alembic (Compose/Render)."
    )


def init_engine(url: str | None = None) -> Engine:
    global _engine
    if url is None:
        url = load_database_url()
    elif url.startswith("sqlite"):
        url = resolve_sqlite_url(url)
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    _engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def ensure_sqlite_schema(url: str | None = None) -> Engine:
    """Apply Alembic ``upgrade head`` for a SQLite URL, then open the engine.

    Refuses non-SQLite URLs so edge never migrates Supabase/Compose Postgres.
    Idempotent when already at head. Used by ``main.py`` on capture and drain.
    """
    if url is None:
        url = load_database_url()
    elif url.startswith("sqlite"):
        url = resolve_sqlite_url(url)
    if not url.startswith("sqlite"):
        raise DatabaseUrlError(
            "ensure_sqlite_schema only applies to SQLite "
            "(edge local prod). Refusing non-SQLite DATABASE_URL."
        )
    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")

    from alembic import command
    from alembic.config import Config

    set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    return init_engine(url)


def get_session() -> Session:
    engine = _engine if _engine is not None else init_engine()
    return Session(engine)
