from __future__ import annotations

from datetime import datetime
from pathlib import Path

from db.config_snapshot import ensure_snapshot_from_json_dir
from db.database import get_session
from db.writes import (
    end_driving_session,
    insert_driving_session,
    insert_local_event,
    insert_operational_exception,
    insert_trip_segment,
    update_trip_segment,
)


class LocalStore:
    def ensure_config_snapshot(self, config_dir: Path) -> int:
        with get_session() as session:
            master_id, _created = ensure_snapshot_from_json_dir(session, config_dir)
            session.commit()
            return master_id

    def start_session(
        self,
        *,
        start_time: datetime,
        master_config_id: int = 1,
        row_id: int | None = None,
    ) -> int:
        with get_session() as session:
            row = insert_driving_session(
                session,
                master_config_id=master_config_id,
                start_time=start_time,
                row_id=row_id,
            )
            session.commit()
            if row.id is None:
                raise RuntimeError("driving_session insert did not assign an id")
            return row.id

    def persist_event(
        self,
        *,
        driving_session_id: int,
        time: datetime,
        type_value: str,
        clip_path: Path,
        fps: int,
        order_number: int,
        num_frames: int,
        clip_start: datetime,
        clip_end: datetime,
        event_id: int | None = None,
        clip_id: int | None = None,
        knn_stage1: tuple[float, ...] | None = None,
        knn_stage2: tuple[float, ...] | None = None,
        approach: dict | None = None,
        trip_segment_id: int | None = None,
        trip_offset_seconds: float | None = None,
    ) -> int:
        with get_session() as session:
            event = insert_local_event(
                session,
                driving_session_id=driving_session_id,
                time=time,
                type_value=type_value,
                clip_path=clip_path,
                fps=fps,
                order_number=order_number,
                num_frames=num_frames,
                clip_start=clip_start,
                clip_end=clip_end,
                row_id=event_id,
                clip_id=clip_id,
                knn_stage1=knn_stage1,
                knn_stage2=knn_stage2,
                approach=approach,
                trip_segment_id=trip_segment_id,
                trip_offset_seconds=trip_offset_seconds,
            )
            session.commit()
            if event.id is None:
                raise RuntimeError("event insert did not assign an id")
            return event.id

    def persist_trip_segment(
        self,
        *,
        driving_session_id: int,
        local_path: Path,
        start_time: datetime,
        end_time: datetime,
        order_number: int,
        row_id: int | None = None,
        init_local_stored: bool | None = True,
    ) -> int:
        with get_session() as session:
            row = insert_trip_segment(
                session,
                driving_session_id=driving_session_id,
                local_path=local_path,
                start_time=start_time,
                end_time=end_time,
                order_number=order_number,
                row_id=row_id,
                init_local_stored=init_local_stored,
            )
            session.commit()
            if row.id is None:
                raise RuntimeError("trip_segment insert did not assign an id")
            return row.id

    def update_trip_segment(
        self,
        segment_id: int,
        *,
        local_path: Path,
        end_time: datetime,
        init_local_stored: bool | None = True,
    ) -> None:
        with get_session() as session:
            update_trip_segment(
                session,
                segment_id,
                local_path=local_path,
                end_time=end_time,
                init_local_stored=init_local_stored,
            )
            session.commit()

    def persist_exception(
        self,
        *,
        driving_session_id: int,
        message: str,
        time: datetime,
        is_fatal: bool,
        row_id: int | None = None,
    ) -> int:
        with get_session() as session:
            row = insert_operational_exception(
                session,
                driving_session_id=driving_session_id,
                message=message,
                time=time,
                is_fatal=is_fatal,
                row_id=row_id,
            )
            session.commit()
            if row.id is None:
                raise RuntimeError("operational_exception insert did not assign an id")
            return row.id

    def end_session(self, session_id: int, *, end_time: datetime) -> None:
        with get_session() as session:
            end_driving_session(session, session_id, end_time=end_time)
            session.commit()
