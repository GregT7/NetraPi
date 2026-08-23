from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel

from app.auth.api_key import require_api_key
from db.database import get_session
from db.models import DrivingSession, MasterConfig

router = APIRouter(
    prefix="/api/netrapi",
    dependencies=[Depends(require_api_key)],
)


class DrivingSessionIn(SQLModel):
    id: int
    master_config_id: int
    start_time: datetime
    end_time: datetime | None = None


@router.post("/driving-session", response_model=DrivingSession)
def upsert_driving_session(payload: DrivingSessionIn) -> DrivingSession:
    with get_session() as session:
        master = session.get(MasterConfig, payload.master_config_id)
        if master is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"master_config_id {payload.master_config_id} not found",
            )
        row = session.get(DrivingSession, payload.id)
        if row is None:
            row = DrivingSession(
                id=payload.id,
                master_config_id=payload.master_config_id,
                start_time=payload.start_time,
                end_time=payload.end_time,
            )
            session.add(row)
        else:
            row.master_config_id = payload.master_config_id
            row.start_time = payload.start_time
            row.end_time = payload.end_time
        session.commit()
        session.refresh(row)
        return row
