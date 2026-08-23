from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, event, pool
from sqlmodel import SQLModel

_MAIN_DIR = Path(__file__).resolve().parents[2]
if str(_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_MAIN_DIR))

from db.database import load_database_url  # noqa: E402
import db.models  # noqa: E402, F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _database_url() -> str:
    return load_database_url(from_process_env=True)


def _configure_context(**kwargs) -> None:
    url = _database_url()
    context.configure(
        target_metadata=target_metadata,
        render_as_batch=url.startswith("sqlite"),
        **kwargs,
    )


def run_migrations_offline() -> None:
    url = _database_url()
    _configure_context(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _database_url()
    # create_engine avoids ConfigParser interpolating % in passwords.
    connectable = create_engine(url, poolclass=pool.NullPool)
    if url.startswith("sqlite"):

        @event.listens_for(connectable, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    with connectable.connect() as connection:
        _configure_context(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
