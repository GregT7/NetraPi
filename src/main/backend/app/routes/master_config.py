from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlmodel import SQLModel

from app.auth.api_key import require_api_key
from db.config_snapshot import find_or_create_snapshot
from db.database import get_session

router = APIRouter(
    prefix="/api/netrapi",
    dependencies=[Depends(require_api_key)],
)


class MasterConfigOut(SQLModel):
    id: int
    created: bool


@router.post("/master-config", response_model=MasterConfigOut)
def find_or_create_master_config(
    payload: dict[str, Any] = Body(...),
) -> MasterConfigOut:
    try:
        with get_session() as session:
            master_id, created = find_or_create_snapshot(session, payload)
            session.commit()
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return MasterConfigOut(id=master_id, created=created)
