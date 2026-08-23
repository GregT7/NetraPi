from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "status": "ok",
        "time": now.isoformat().replace("+00:00", "Z"),
    }
