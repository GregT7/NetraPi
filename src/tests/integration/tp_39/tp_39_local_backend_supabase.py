"""
TP-39: Local backend can reach Supabase (integration).

Loads DATABASE_URL from the backend `.env` (same Settings as FastAPI) and
runs SELECT 1. No extra HTTP route. Distinct from TP-33, which talks to
Postgres without using app.config. Does not use Compose DATABASE_URL
(local Postgres stand-in).

Usage (from repo root, venv with sqlalchemy + psycopg2-binary):

    python src/tests/integration/tp_39/tp_39_local_backend_supabase.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
MAIN_DIR = REPO_ROOT / "src" / "main"
BACKEND_DIR = MAIN_DIR / "backend"


def _configure_import_path() -> None:
    for entry in (str(MAIN_DIR), str(BACKEND_DIR)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _load_backend_settings():
    from pydantic import ValidationError

    from app.config import Settings, get_settings

    saved_url = os.environ.pop("DATABASE_URL", None)
    saved_key = os.environ.pop("NETRAPI_API_KEY", None)
    try:
        get_settings.cache_clear()
        try:
            settings = Settings(_env_file=BACKEND_DIR / ".env")
        except ValidationError:
            raise RuntimeError(
                "src/main/backend/.env must set DATABASE_URL and NETRAPI_API_KEY"
            )
        url = (settings.database_url or "").strip()
        if not url.lower().startswith("postgresql"):
            raise RuntimeError(
                "backend .env DATABASE_URL must be the Supabase postgresql URI"
            )
        return settings
    finally:
        if saved_url is not None:
            os.environ["DATABASE_URL"] = saved_url
        if saved_key is not None:
            os.environ["NETRAPI_API_KEY"] = saved_key
        get_settings.cache_clear()


def main() -> int:
    _configure_import_path()
    print("TP-39: Local backend can reach Supabase", flush=True)
    print("  1. Load DATABASE_URL from backend Settings", flush=True)
    print("  2. Connect and run SELECT 1", flush=True)

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url

        settings = _load_backend_settings()
        url = settings.database_url
        parsed = make_url(url)
        engine = create_engine(url, pool_pre_ping=True)
        try:
            with engine.connect() as connection:
                value = connection.execute(text("SELECT 1")).scalar()
                dialect = engine.dialect.name
                host = parsed.host
        finally:
            engine.dispose()
        if value != 1:
            raise RuntimeError(f"SELECT 1 returned {value!r}")
        if dialect != "postgresql":
            raise RuntimeError(f"expected postgresql, got {dialect}")
        body = {"ok": True, "result": value, "dialect": dialect, "host": host}
        print(json.dumps(body, indent=2), flush=True)
    except ModuleNotFoundError as exc:
        print(
            "FAIL: Postgres driver missing. Recreate the venv with src/create_env.bat "
            f"or pip install psycopg2-binary==2.9.10 ({exc})",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: backend SELECT 1 succeeded against Supabase Postgres")
    print("  reminder: do not put these credentials on the Pi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
