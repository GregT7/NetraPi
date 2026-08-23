from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ConfigDict
from sqlmodel import SQLModel

from app.auth.api_key import require_api_key
from db.database import get_session
from db.models import DrivingSession, TripSegment

router = APIRouter(
    prefix="/api/netrapi",
    dependencies=[Depends(require_api_key)],
)


class TripSegmentIn(SQLModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    driving_session_id: int
    local_path: Optional[str] = None
    init_local_stored: Optional[bool] = None
    file_size_bytes: Optional[int] = None
    start_time: datetime
    end_time: datetime
    order_number: int


@router.post("/trip-segment", response_model=TripSegment)
def upsert_trip_segment(payload: TripSegmentIn) -> TripSegment:
    with get_session() as session:
        if session.get(DrivingSession, payload.driving_session_id) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"driving_session {payload.driving_session_id} not found",
            )
        row = session.get(TripSegment, payload.id)
        if row is None:
            row = TripSegment(
                id=payload.id,
                driving_session_id=payload.driving_session_id,
                local_path=payload.local_path,
                init_local_stored=payload.init_local_stored,
                file_size_bytes=payload.file_size_bytes,
                start_time=payload.start_time,
                end_time=payload.end_time,
                order_number=payload.order_number,
                s3_key=None,
                s3_stored=None,
                init_local_deleted=None,
            )
            session.add(row)
        else:
            row.driving_session_id = payload.driving_session_id
            row.init_local_stored = payload.init_local_stored
            row.start_time = payload.start_time
            row.end_time = payload.end_time
            row.order_number = payload.order_number
            if payload.file_size_bytes is not None:
                row.file_size_bytes = payload.file_size_bytes
            if row.init_local_deleted is not True:
                row.local_path = payload.local_path
        session.commit()
        session.refresh(row)
        return row
