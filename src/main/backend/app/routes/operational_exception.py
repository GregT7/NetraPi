from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import SQLModel

from app.auth.api_key import require_api_key
from db.database import get_session
from db.models import DrivingSession, OperationalException

router = APIRouter(
    prefix="/api/netrapi",
    dependencies=[Depends(require_api_key)],
)


class OperationalExceptionIn(SQLModel):
    id: int
    driving_session_id: int
    message: str
    time: datetime
    is_fatal: bool


@router.post("/operational-exception", response_model=OperationalException)
def upsert_operational_exception(payload: OperationalExceptionIn) -> OperationalException:
    with get_session() as session:
        if session.get(DrivingSession, payload.driving_session_id) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"driving_session {payload.driving_session_id} not found",
            )
        row = session.get(OperationalException, payload.id)
        if row is None:
            row = OperationalException(
                id=payload.id,
                driving_session_id=payload.driving_session_id,
                message=payload.message,
                time=payload.time,
                is_fatal=payload.is_fatal,
            )
            session.add(row)
        else:
            row.driving_session_id = payload.driving_session_id
            row.message = payload.message
            row.time = payload.time
            row.is_fatal = payload.is_fatal
        session.commit()
        session.refresh(row)
        return row
