"""
TP-33: Supabase project and Postgres connectivity (integration).

Connects from this development machine and runs SELECT 1 using
DATABASE_URL in `src/main/backend/.env` (gitignored). Does not start
FastAPI and does not use edge/Pi config.

Usage (from repo root, venv with sqlalchemy + psycopg2-binary):

    python src/tests/integration/tp_33/tp_33_supabase_postgres_connectivity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
BACKEND_ENV_PATH = REPO_ROOT / "src" / "main" / "backend" / ".env"


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


def _database_url_from_backend_env() -> str:
    if not BACKEND_ENV_PATH.is_file():
        raise RuntimeError(f"missing {BACKEND_ENV_PATH}")
    url = _parse_env_file(BACKEND_ENV_PATH).get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            f"DATABASE_URL is missing in {BACKEND_ENV_PATH}. "
            "Put the Supabase postgresql+psycopg2 URI there."
        )
    if not url.lower().startswith("postgresql"):
        raise RuntimeError(
            "backend .env DATABASE_URL must be the Supabase postgresql URI"
        )
    return url


def _run_select_one(url: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            value = connection.execute(text("SELECT 1")).scalar()
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Postgres driver missing. Recreate the venv with src/create_env.bat "
            "or pip install psycopg2-binary==2.9.10"
        ) from exc
    finally:
        engine.dispose()

    if value != 1:
        raise RuntimeError(f"SELECT 1 returned {value!r}, expected 1")


def main() -> int:
    print("TP-33: Supabase project and Postgres connectivity", flush=True)
    print("  1. Load DATABASE_URL from backend .env (not FastAPI, not the Pi)", flush=True)
    print("  2. Connect and run SELECT 1", flush=True)

    try:
        from sqlalchemy.engine import make_url

        url = _database_url_from_backend_env()
        parsed = make_url(url)
        print(f"  connect: {parsed.render_as_string(hide_password=True)}", flush=True)
        print(f"  host: {parsed.host}  source: {BACKEND_ENV_PATH}", flush=True)
        _run_select_one(url)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: SELECT 1 succeeded against Supabase Postgres")
    print("  reminder: do not put these credentials on the Pi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
