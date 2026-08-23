"""
TP-54: Cross-layer metadata consistency (system).

Reads the SQLite DB left by TP-53 and checks event / clip / trip identity
fields are internally consistent after a successful CloudIngest confirm
(``s3_stored``, matching keys and sizes). Does not load backend ``.env``;
optional live Postgres/S3 console checks are documented in AT-7.1 README.

Usage (from repo root):

    python src/tests/integration/tp_54/tp_54_cross_layer_metadata.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import configure_import_path, sqlite_url  # noqa: E402

TP53_DB = SCRIPT_DIR.parent / "tp_53" / "netrapi.db"


def main() -> int:
    configure_import_path()
    print("TP-54: Cross-layer metadata consistency", flush=True)
    print("  1. Inspect TP-53 SQLite event / clip / trip", flush=True)
    print("  2. Confirm s3_stored keys and sizes are consistent", flush=True)
    print("  3. (Optional) Postgres/S3 console — AT-7.1 README", flush=True)

    if not TP53_DB.is_file():
        print(
            f"FAIL: {TP53_DB} not found. Run TP-53 first.",
            file=sys.stderr,
        )
        return 1

    try:
        from sqlmodel import Session, create_engine, select

        from db.models import Clip, Event, EventTripLocation, TripSegment

        engine = create_engine(sqlite_url(TP53_DB))
        try:
            with Session(engine) as local:
                event = local.exec(select(Event).order_by(Event.id.desc())).first()
                if event is None or event.id is None:
                    raise RuntimeError("TP-53 sqlite has no event row")
                clip = local.exec(select(Clip).where(Clip.event_id == event.id)).first()
                if clip is None or clip.id is None:
                    raise RuntimeError("TP-53 sqlite clip missing")
                if clip.s3_stored is not True or not clip.s3_key:
                    raise RuntimeError("TP-53 sqlite clip is not S3-confirmed")
                if clip.file_size_bytes is None or clip.file_size_bytes <= 0:
                    raise RuntimeError(f"TP-53 clip file_size_bytes {clip.file_size_bytes!r}")

                trip = local.exec(
                    select(TripSegment).where(
                        TripSegment.driving_session_id == event.driving_session_id
                    )
                ).first()
                if trip is None or trip.id is None:
                    raise RuntimeError("TP-53 sqlite trip_segment missing")
                if trip.s3_stored is not True or not trip.s3_key:
                    raise RuntimeError("TP-53 sqlite trip is not S3-confirmed")
                if trip.s3_key == clip.s3_key:
                    raise RuntimeError("clip and trip share the same s3_key")

                loc = local.exec(
                    select(EventTripLocation).where(EventTripLocation.event_id == event.id)
                ).first()
                if loc is None or loc.trip_segment_id != trip.id:
                    raise RuntimeError("TP-53 event_trip_location missing or mismatched")

                print(
                    f"  sqlite event {event.id} session {event.driving_session_id} "
                    f"clip {clip.id} key {clip.s3_key} size {clip.file_size_bytes}",
                    flush=True,
                )
                print(
                    f"  sqlite trip {trip.id} key {trip.s3_key} "
                    f"linked via event_trip_location",
                    flush=True,
                )
                object_key = clip.s3_key
                trip_key = trip.s3_key
        finally:
            engine.dispose()

        print(f"  clip s3_key: {object_key}", flush=True)
        print(f"  trip s3_key: {trip_key}", flush=True)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: TP-53 sqlite event/clip/trip ids and s3 keys are consistent")
    print("  optional Postgres/S3 console: see AT-7.1 README")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
