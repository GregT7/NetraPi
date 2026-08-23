from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from netrapi.exceptions import IngestAuthError

API_KEY_HEADER_NAME = "X-API-Key"
_EDGE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = _EDGE_DIR / ".env"

_auth: IngestAuth | None = None


@dataclass(frozen=True)
class IngestAuth:
    api_url: str
    api_key: str


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            values[key] = value
    return values


def apply_edge_env() -> None:
    """Copy unset keys from edge/.env into the process environment. Call once at start."""
    if not ENV_PATH.is_file():
        return
    for key, value in _parse_env_file(ENV_PATH).items():
        if not (os.environ.get(key) or "").strip():
            os.environ[key] = value


def load_ingest_auth() -> IngestAuth:
    """Snapshot URL and key from the process environment. Call once before ingest."""
    global _auth
    if _auth is not None:
        return _auth
    url = (os.environ.get("NETRAPI_API_URL") or "").strip().rstrip("/")
    key = (os.environ.get("NETRAPI_API_KEY") or "").strip()
    missing = [
        name
        for name, value in (("NETRAPI_API_URL", url), ("NETRAPI_API_KEY", key))
        if not value
    ]
    if missing:
        raise IngestAuthError(
            f"{', '.join(missing)} not set in the process environment. "
            "Export them, or put them in src/main/edge/.env and call apply_edge_env() "
            "at process start."
        )
    _auth = IngestAuth(api_url=url, api_key=key)
    return _auth


def clear_ingest_auth() -> None:
    global _auth
    _auth = None


def ingest_api_url() -> str:
    if _auth is None:
        raise IngestAuthError("ingest auth not loaded; call load_ingest_auth() first")
    return _auth.api_url


def ingest_headers() -> dict[str, str]:
    if _auth is None:
        raise IngestAuthError("ingest auth not loaded; call load_ingest_auth() first")
    return {API_KEY_HEADER_NAME: _auth.api_key}
