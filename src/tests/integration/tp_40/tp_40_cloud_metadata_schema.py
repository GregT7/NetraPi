"""
TP-40: Cloud metadata schema deployment (integration).

Loads DATABASE_URL from backend Settings, applies Alembic `upgrade head`
against that Postgres URL, then inspects operational tables and S3 path
columns. Does not start FastAPI and does not use Compose DATABASE_URL.

Usage (from repo root, venv with alembic + sqlalchemy + psycopg2-binary):

    python src/tests/integration/tp_40/tp_40_cloud_metadata_schema.py
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
DB_DIR = MAIN_DIR / "db"
ALEMBIC_INI = DB_DIR / "alembic.ini"

REQUIRED_TABLES = (
    "driving_session",
    "event",
    "clip",
    "classification",
    "auto_classification",
    "trip_segment",
)

REQUIRED_COLUMNS = {
    "event": ("id", "driving_session_id", "time"),
    "clip": ("id", "event_id", "local_path", "s3_key", "s3_stored", "file_size_bytes", "init_local_deleted"),
    "trip_segment": ("id", "local_path", "s3_key", "s3_stored", "file_size_bytes", "init_local_deleted"),
}


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


def _upgrade_head(url: str) -> str:
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")
    from db.database import set_database_url_override

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    set_database_url_override(url)
    try:
        config = Config(str(ALEMBIC_INI))
        command.upgrade(config, "head")
        head = ScriptDirectory.from_config(config).get_current_head()
    finally:
        set_database_url_override(None)
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
    if not head:
        raise RuntimeError("Alembic head revision is empty")
    return head


def _column_names(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def main() -> int:
    _configure_import_path()
    print("TP-40: Cloud metadata schema deployment", flush=True)
    print("  1. Load DATABASE_URL from backend Settings", flush=True)
    print("  2. Alembic upgrade head against Supabase", flush=True)
    print("  3. Inspect event tables and S3 path columns", flush=True)

    try:
        from sqlalchemy import create_engine, inspect, text
        from sqlalchemy.engine import make_url

        settings = _load_backend_settings()
        url = settings.database_url
        parsed = make_url(url)
        print(
            f"  connect: {parsed.render_as_string(hide_password=True)}",
            flush=True,
        )

        head = _upgrade_head(url)
        engine = create_engine(url, pool_pre_ping=True)
        try:
            inspector = inspect(engine)
            tables = set(inspector.get_table_names())
            missing_tables = [name for name in REQUIRED_TABLES if name not in tables]
            if missing_tables:
                raise RuntimeError("missing tables: " + ", ".join(missing_tables))
            missing_columns: list[str] = []
            for table, columns in REQUIRED_COLUMNS.items():
                present = _column_names(inspector, table)
                for column in columns:
                    if column not in present:
                        missing_columns.append(f"{table}.{column}")
            if missing_columns:
                raise RuntimeError("missing columns: " + ", ".join(missing_columns))
            with engine.connect() as connection:
                version = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar()
        finally:
            engine.dispose()
        if version != head:
            raise RuntimeError(
                f"alembic_version {version!r} does not match head {head!r}"
            )
        body = {
            "ok": True,
            "host": parsed.host,
            "alembic_head": head,
            "tables": list(REQUIRED_TABLES),
            "s3_path_columns": ["clip.s3_key", "trip_segment.s3_key"],
        }
        print(json.dumps(body, indent=2), flush=True)
    except ModuleNotFoundError as exc:
        print(
            "FAIL: Postgres driver or Alembic missing. Recreate the venv with "
            f"src/create_env.bat ({exc})",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: Supabase schema has event metadata tables and S3 path columns")
    print("  reminder: do not put these credentials on the Pi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
