"""
TP-59: Authenticated GET /api/netrapi/ready (integration).

Against Render: GET /health stays open. GET /api/netrapi/ready without a
key or with a wrong key is 401. A valid X-API-Key returns 200 (both
layers ok) or 503 with per-layer status.

Needs NETRAPI_API_KEY (and optional NETRAPI_API_URL) in
src/main/edge/.env matching Render. Does not use backend .env.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import (  # noqa: E402
    apply_edge_ingest_auth,
    configure_import_path,
    http_json,
    wait_health,
)

configure_import_path()


def _print(label: str, response) -> None:
    print(f"  {label} -> {response.status_code}", flush=True)
    text = (response.text or "").strip()
    if not text:
        return
    try:
        print(json.dumps(response.json(), indent=2), flush=True)
    except Exception:
        print(text[:500], flush=True)


def main() -> int:
    from netrapi.backend_auth import ingest_headers

    print("TP-59: Authenticated /api/netrapi/ready (Postgres + S3)", flush=True)
    print("  1. GET /health without an API key", flush=True)
    print("  2. GET /api/netrapi/ready without a key", flush=True)
    print("  3. GET /api/netrapi/ready with a wrong key", flush=True)
    print("  4. GET /api/netrapi/ready with a valid X-API-Key", flush=True)

    origin = apply_edge_ingest_auth()
    print(f"  origin: {origin}", flush=True)
    wait_health(origin)
    valid = {**ingest_headers(), "Accept": "application/json"}

    health = http_json(origin, "GET", "/health")
    _print("GET /health (no key)", health)
    if health.status_code != 200 or health.json().get("status") != "ok":
        raise RuntimeError(f"GET /health failed: {health.status_code} {health.text}")

    missing = http_json(origin, "GET", "/api/netrapi/ready")
    _print("GET /ready (no key)", missing)
    if missing.status_code != 401:
        raise RuntimeError(
            f"missing key should be 401, got {missing.status_code}: {missing.text}"
        )

    wrong = http_json(
        origin,
        "GET",
        "/api/netrapi/ready",
        headers={"X-API-Key": "wrong-key", "Accept": "application/json"},
    )
    _print("GET /ready (wrong key)", wrong)
    if wrong.status_code != 401:
        raise RuntimeError(
            f"wrong key should be 401, got {wrong.status_code}: {wrong.text}"
        )

    ready = http_json(origin, "GET", "/api/netrapi/ready", headers=valid)
    _print("GET /ready (valid X-API-Key)", ready)
    body = ready.json()
    if "database" not in body or "s3" not in body:
        raise RuntimeError(f"ready body missing layers: {body!r}")
    if ready.status_code == 200:
        if body.get("status") != "ok" or body.get("database") != "ok" or body.get("s3") != "ok":
            raise RuntimeError(f"200 ready should be all ok: {body!r}")
    elif ready.status_code == 503:
        if body.get("status") != "error":
            raise RuntimeError(f"503 ready should set status=error: {body!r}")
        print("  note: deployed stack returned 503; per-layer status is present", flush=True)
    else:
        raise RuntimeError(
            f"valid key should be 200 or 503, got {ready.status_code}: {ready.text}"
        )

    print(
        "PASS: /health open; /api/netrapi/ready requires X-API-Key and reports DB+S3",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
