"""
TP-41: Trip recording persists trip_segment rows (integration).

Enables full-session trip recording, writes at least one segment file, and
checks SQLite for a trip_segment row (local_path on disk, s3 flags null).

Usage (from repo root, Pi edge venv with Coral + ffmpeg):

    python src/tests/integration/tp_41/tp_41_trip_segment_sqlite.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
MAIN_DIR = SCRIPT_DIR.parents[2] / "main"
EDGE_DIR = MAIN_DIR / "edge"
DB_DIR = MAIN_DIR / "db"
ALEMBIC_INI = DB_DIR / "alembic.ini"
OUTPUT_DB_PATH = SCRIPT_DIR / "netrapi.db"

VERIFY_TPU = False
PREVIEW_ENABLED = False
MAX_LAPS = 12
SEGMENT_SECONDS = 300


class _FakeCamera:
    def __init__(self, frame: np.ndarray, *, capture_fps: float = 30.0) -> None:
        self._frame = frame
        self.capture_fps = capture_fps

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def read(self) -> np.ndarray:
        return self._frame.copy()

    def measure_fps(self, *, apply: bool = False) -> float:
        if apply:
            self.capture_fps = 30.0
        return self.capture_fps


class _IdleEventStub:
    @property
    def needs_detection(self) -> bool:
        return False

    @property
    def ready_to_evaluate(self) -> bool:
        return False

    def observe(self, pre_buffer, *, now=None) -> None:
        return None

    def evaluate(self):
        raise RuntimeError("evaluate should not run in TP-41")


def _configure_import_path() -> None:
    for path in (MAIN_DIR, EDGE_DIR):
        path_str = str(path)
        if path_str in sys.path:
            sys.path.remove(path_str)
    sys.path.insert(0, str(MAIN_DIR))
    sys.path.insert(0, str(EDGE_DIR))


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _init_schema(url: str) -> None:
    from alembic import command
    from alembic.config import Config
    from db.database import set_database_url_override

    if not ALEMBIC_INI.is_file():
        raise RuntimeError(f"Alembic config not found: {ALEMBIC_INI}")
    set_database_url_override(url)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def _remove_lgpio_notify_pipes(*directories: Path) -> None:
    seen: set[Path] = set()
    for directory in directories:
        try:
            resolved = directory.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        for path in resolved.glob(".lgd-nfy*"):
            try:
                path.unlink()
            except OSError:
                pass


def _apply_test_config(app_config, *, repo_root: Path, resolve_runtime_paths: Callable):
    app_config = resolve_runtime_paths(app_config, repo_root)
    trip = app_config.trip_recorder
    segments_dir = SCRIPT_DIR / "trips"
    app_config = replace(
        app_config,
        trip_recorder=replace(
            trip,
            enabled=True,
            segments_dir=segments_dir,
            segment_seconds=SEGMENT_SECONDS,
        ),
        preview=replace(app_config.preview, enabled=PREVIEW_ENABLED),
    )
    return app_config


def _inspect_trip(session) -> Path:
    from sqlmodel import select

    from db.models import DrivingSession, Event, TripSegment

    sessions = session.exec(select(DrivingSession)).all()
    if len(sessions) != 1:
        raise AssertionError(f"expected 1 driving_session, got {len(sessions)}")
    events = session.exec(select(Event)).all()
    if events:
        raise AssertionError("TP-41 should not insert events")
    rows = session.exec(select(TripSegment).order_by(TripSegment.order_number)).all()
    if not rows:
        raise AssertionError("no trip_segment row")
    row = rows[0]
    if row.driving_session_id != sessions[0].id:
        raise AssertionError("trip_segment.driving_session_id mismatch")
    if row.order_number < 1:
        raise AssertionError(f"order_number {row.order_number}")
    if not row.local_path:
        raise AssertionError("trip_segment.local_path missing")
    path = Path(row.local_path)
    if not path.is_file():
        raise AssertionError(f"trip file missing: {path}")
    if row.s3_key is not None or row.s3_stored is not None:
        raise AssertionError("trip s3 fields must stay null")
    print(
        f"  trip_segment id={row.id} order={row.order_number} path={row.local_path}"
    )
    return path


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi import build_pipeline
    from netrapi.exceptions import NetraPiError

    import db.database as database
    from db.database import get_session, init_engine

    print("TP-41: Trip segment SQLite persist", flush=True)
    print("  1. Initialize SQLite", flush=True)
    print("  2. Run full-record loop; stop finalizes a segment", flush=True)
    print("  3. Query trip_segment", flush=True)

    try:
        base_config = AppConfig.load(DEFAULT_CONFIG_DIR.resolve())
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    try:
        if OUTPUT_DB_PATH.exists():
            OUTPUT_DB_PATH.unlink()
        url = _sqlite_url(OUTPUT_DB_PATH)
        print(f"  sqlite: {OUTPUT_DB_PATH}")
        _init_schema(url)
        init_engine(url)

        app_config = _apply_test_config(
            base_config,
            repo_root=REPO_ROOT,
            resolve_runtime_paths=_resolve_runtime_paths,
        )
        app_config.trip_recorder.segments_dir.mkdir(parents=True, exist_ok=True)
        pipeline = build_pipeline(app_config, verify_tpu=VERIFY_TPU)
        manager = pipeline.manager
        cam = app_config.camera
        frame = np.zeros((cam.height, cam.width, cam.channels), dtype=np.uint8)
        manager._camera = _FakeCamera(frame, capture_fps=float(cam.recommended_fps))
        manager._event_manager = _IdleEventStub()
        manager.run_loop(max_laps=MAX_LAPS, full_record=True)

        with get_session() as session:
            path = _inspect_trip(session)
        if database._engine is not None:
            database._engine.dispose()
        database._engine = None
    except NetraPiError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        _remove_lgpio_notify_pipes(SCRIPT_DIR, Path.cwd())
        database.set_database_url_override(None)

    print("PASS: trip_segment row matches the local file")
    print(f"  inspect db: {OUTPUT_DB_PATH}")
    print(f"  inspect trip: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
