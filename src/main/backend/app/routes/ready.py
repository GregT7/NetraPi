from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth.api_key import require_api_key
from app.s3 import head_bucket
from db.database import get_session

router = APIRouter(
    prefix="/api/netrapi",
    dependencies=[Depends(require_api_key)],
)


@router.get("/ready")
def ready() -> JSONResponse:
    db_status = "ok"
    s3_status = "ok"
    detail: dict[str, str] = {}

    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "error"
        detail["database"] = str(exc)

    try:
        head_bucket()
    except Exception as exc:
        s3_status = "error"
        detail["s3"] = str(exc)

    body: dict[str, object] = {
        "status": "ok" if db_status == "ok" and s3_status == "ok" else "error",
        "database": db_status,
        "s3": s3_status,
    }
    if detail:
        body["detail"] = detail
    code = status.HTTP_200_OK if body["status"] == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=code, content=body)
