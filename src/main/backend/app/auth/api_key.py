from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

API_KEY_HEADER_NAME = "X-API-Key"

_API_KEY_HEADER = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def require_api_key(
    api_key: str | None = Depends(_API_KEY_HEADER),
) -> str:
    expected = get_settings().netrapi_api_key
    provided = (api_key or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return provided
