"""Apply Alembic revisions to Pi SQLite or Supabase Postgres.

Cloud always reads DATABASE_URL from src/main/backend/.env on disk.
SQLite always reads src/main/edge/.env. Process DATABASE_URL is ignored.

From src/main/db (backend venv for cloud):

    python apply.py sqlite
    python apply.py cloud
    python apply.py current sqlite
    python apply.py current cloud
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

_MAIN_DIR = Path(__file__).resolve().parent.parent
if str(_MAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_MAIN_DIR))

from db.database import (  # noqa: E402
    ALEMBIC_INI,
    parse_env_file,
    resolve_sqlite_url,
    set_database_url_override,
)

_BACKEND_ENV = _MAIN_DIR / "backend" / ".env"
_EDGE_ENV = _MAIN_DIR / "edge" / ".env"


def _redact_url(url: str) -> str:
    if url.lower().startswith("sqlite"):
        return url
    parsed = urlparse(url)
    host = parsed.hostname or "?"
    dbname = parsed.path.lstrip("/") or "?"
    return f"{parsed.scheme}://{host}/{dbname}"


def _database_url(target: str) -> str:
    if target == "cloud":
        env_path = _BACKEND_ENV
        kind = "postgresql"
    elif target == "sqlite":
        env_path = _EDGE_ENV
        kind = "sqlite"
    else:
        raise SystemExit(f"unknown target {target!r}; use sqlite or cloud")

    if not env_path.is_file():
        raise SystemExit(f"missing {env_path}")
    url = parse_env_file(env_path).get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit(f"{env_path} has no DATABASE_URL")
    if kind == "postgresql":
        if not url.lower().startswith("postgresql"):
            raise SystemExit(
                f"cloud target requires a postgresql DATABASE_URL in {env_path}"
            )
        return url
    if not url.lower().startswith("sqlite"):
        raise SystemExit(f"sqlite target requires a sqlite DATABASE_URL in {env_path}")
    return resolve_sqlite_url(url)


def _alembic_config():
    from alembic.config import Config

    if not ALEMBIC_INI.is_file():
        raise SystemExit(f"Alembic config not found: {ALEMBIC_INI}")
    return Config(str(ALEMBIC_INI))


def _upgrade(target: str) -> None:
    from alembic import command

    url = _database_url(target)
    set_database_url_override(url)
    print(f"applying head to {_redact_url(url)}")
    command.upgrade(_alembic_config(), "head")
    _current(target)


def _current(target: str) -> None:
    from alembic import command

    url = _database_url(target)
    set_database_url_override(url)
    print(f"current on {_redact_url(url)}")
    command.current(_alembic_config())


def main(argv: list[str]) -> int:
    if len(argv) == 1 and argv[0] in {"sqlite", "cloud"}:
        _upgrade(argv[0])
        return 0
    if len(argv) == 2 and argv[0] == "current" and argv[1] in {"sqlite", "cloud"}:
        _current(argv[1])
        return 0
    print(
        "usage: python apply.py sqlite|cloud\n"
        "       python apply.py current sqlite|cloud",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
