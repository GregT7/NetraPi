from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3]
_MAIN = _SRC / "main"

if str(_MAIN) not in sys.path:
    sys.path.insert(0, str(_MAIN))


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'netrapi.db').resolve().as_posix()}"


@pytest.fixture(autouse=True)
def _reset_db_engine() -> Iterator[None]:
    import db.database as database

    yield
    database.set_database_url_override(None)
    if database._engine is not None:
        database._engine.dispose()
        database._engine = None
