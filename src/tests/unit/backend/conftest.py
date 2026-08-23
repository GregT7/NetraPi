from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_SRC = Path(__file__).resolve().parents[3]
_MAIN = _SRC / "main"
_BACKEND = _MAIN / "backend"
ALEMBIC_INI = _MAIN / "db" / "alembic.ini"
UNIT_API_KEY = "unit-test-netrapi-key"
UNIT_HEADERS = {"X-API-Key": UNIT_API_KEY}

for _entry in (str(_MAIN), str(_BACKEND)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)


@pytest.fixture
def memory_database_url(monkeypatch: pytest.MonkeyPatch) -> str:
    url = "sqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", url)
    from app.config import get_settings

    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("NETRAPI_API_KEY", UNIT_API_KEY)
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_db_engine() -> Iterator[None]:
    import db.database as database

    yield
    database.set_database_url_override(None)
    if database._engine is not None:
        database._engine.dispose()
        database._engine = None


@pytest.fixture
def ingest_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    url = f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("NETRAPI_API_KEY", UNIT_API_KEY)
    from alembic import command
    from alembic.config import Config

    from app.config import get_settings
    from app.main import create_app
    from db.database import set_database_url_override

    get_settings.cache_clear()
    set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()
