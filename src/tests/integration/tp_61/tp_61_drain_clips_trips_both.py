"""
TP-61: Drain clips, trips, or both, then optional --delete-uploaded.

Checks CLI targets, drain order, /health wake before upload, and
``--drain … --delete-uploaded`` after a successful drain.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlmodel import select

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import configure_import_path, init_sqlite, sqlite_url  # noqa: E402

configure_import_path()


def _reset_engine() -> None:
    import db.database as database

    database.set_database_url_override(None)
    if database._engine is not None:
        database._engine.dispose()
        database._engine = None


def _check_cli() -> None:
    from main import main as edge_main
    from main import parse_args

    print("  1. --drain without a target is an error", flush=True)
    try:
        parse_args(["--drain"])
    except SystemExit:
        pass
    else:
        raise RuntimeError("--drain without a target should exit")

    print("  2. --drain with --delete-all exits 1", flush=True)
    if edge_main(["--drain", "both", "--delete-all"]) != 1:
        raise RuntimeError("--drain with --delete-all should exit 1")

    print("  3. clips / trips / both drain in order; both then delete-uploaded", flush=True)
    ingest = MagicMock()
    order: list[str] = []
    ingest.drain_clips.side_effect = lambda: order.append("clips") or 1
    ingest.drain_trip_segments.side_effect = lambda: order.append("trips") or 2
    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.ensure_sqlite_schema"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.health.wake_render", return_value=True),
        patch("netrapi.build_pipeline") as build,
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch("netrapi.local_cleanup.delete_uploaded_local_media") as cleanup,
    ):
        cleanup.side_effect = lambda *_a, **_k: order.append("delete") or 1
        if edge_main(["--drain", "clips"]) != 0:
            raise RuntimeError("clips drain should exit 0")
        if ingest.drain_trip_segments.called:
            raise RuntimeError("clips drain should not upload trips")
        ingest.drain_clips.reset_mock()
        ingest.drain_trip_segments.reset_mock()
        if edge_main(["--drain", "trips"]) != 0:
            raise RuntimeError("trips drain should exit 0")
        if ingest.drain_clips.called:
            raise RuntimeError("trips drain should not upload clips")
        order.clear()
        if edge_main(["--drain", "both", "--delete-uploaded"]) != 0:
            raise RuntimeError("both drain + delete-uploaded should exit 0")
        if order != ["clips", "trips", "delete"]:
            raise RuntimeError(f"expected clips, trips, delete; got {order}")
        cleanup.assert_called_with(ingest)
        if build.called:
            raise RuntimeError("drain must not start capture")

    print("  4. /health wake failure skips drain and delete", flush=True)
    ingest = MagicMock()
    with (
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("db.database.ensure_sqlite_schema"),
        patch("netrapi.cloud_ingest.try_cloud_ingest", return_value=ingest),
        patch("netrapi.health.wake_render", return_value=False),
        patch("netrapi.build_pipeline"),
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch("netrapi.local_cleanup.delete_uploaded_local_media") as cleanup,
    ):
        if edge_main(["--drain", "both", "--delete-uploaded"]) != 1:
            raise RuntimeError("wake failure should exit 1")
        ingest.drain_clips.assert_not_called()
        ingest.drain_trip_segments.assert_not_called()
        cleanup.assert_not_called()


def _check_scoped_delete(tmp_dir: Path) -> None:
    from db.database import get_session
    from db.models import Clip, TripSegment
    from db.writes import insert_driving_session, insert_local_event, insert_trip_segment
    from netrapi.cloud_ingest import CloudIngest
    from netrapi.local_cleanup import delete_uploaded_local_media

    print("  5. Scoped delete (clips) leaves uploaded trip files", flush=True)
    db_path = tmp_dir / "netrapi.db"
    url = sqlite_url(db_path)
    init_sqlite(url)
    clip_file = tmp_dir / "clip.mp4"
    trip_file = tmp_dir / "trip.mp4"
    clip_file.write_bytes(b"clip")
    trip_file.write_bytes(b"trip")
    started = datetime(2026, 8, 23, 18, 0, 0)
    calls: list[tuple] = []

    def json_request(method: str, path: str, body):
        calls.append((method, path, body))
        return {"ok": True}

    ingest = CloudIngest(json_request=json_request, put_file=lambda *_: None)
    with get_session() as session:
        driving = insert_driving_session(session, start_time=started)
        event = insert_local_event(
            session,
            driving_session_id=driving.id,
            time=started + timedelta(seconds=1),
            type_value="rolling-stop",
            clip_path=clip_file,
            fps=30,
            order_number=1,
            num_frames=30,
            clip_start=started,
            clip_end=started + timedelta(seconds=1),
        )
        session.commit()
        clip = session.exec(select(Clip).where(Clip.event_id == event.id)).first()
        assert clip is not None
        clip.s3_key = "Aug-2026/driving_session_id_1/clips/clip-1.mp4"
        clip.s3_stored = True
        session.add(clip)
        trip = insert_trip_segment(
            session,
            driving_session_id=driving.id,
            local_path=trip_file,
            start_time=started,
            end_time=started + timedelta(seconds=5),
            order_number=1,
        )
        trip.s3_key = "Aug-2026/driving_session_id_1/trips/trip-1.mp4"
        trip.s3_stored = True
        session.add(trip)
        session.commit()

    cleaned = delete_uploaded_local_media(ingest, target="clips")
    if cleaned != 1:
        raise RuntimeError(f"expected 1 clip deleted, got {cleaned}")
    if clip_file.is_file():
        raise RuntimeError("clip MP4 should be gone")
    if not trip_file.is_file():
        raise RuntimeError("trip MP4 should remain for target=clips")


def main() -> int:
    print("TP-61: Drain clips, trips, or both + delete-uploaded", flush=True)
    _check_cli()
    tmp_dir = SCRIPT_DIR / "_tmp"
    tmp_dir.mkdir(exist_ok=True)
    try:
        _check_scoped_delete(tmp_dir)
    finally:
        _reset_engine()
        for leftover in tmp_dir.glob("*"):
            leftover.unlink(missing_ok=True)
        tmp_dir.rmdir()
    print("PASS: drain targets, wake-before-upload, delete-uploaded after drain", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _reset_engine()
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
