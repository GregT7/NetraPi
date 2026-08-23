"""
TP-51: Backend deployment to hosting environment (integration).

Confirms the deployed Render service is reachable via GET /health.
Reads ``NETRAPI_API_URL`` from ``src/main/edge/.env`` when unset
(default https://netrapi.onrender.com). Does not use backend ``.env``.

Usage (from repo root):

    python src/tests/integration/tp_51/tp_51_backend_deployment.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import api_origin, configure_import_path, wait_health  # noqa: E402


def main() -> int:
    configure_import_path()
    from netrapi.backend_auth import apply_edge_env

    apply_edge_env()
    origin = api_origin()
    print("TP-51: Backend deployment to hosting environment", flush=True)
    print(f"  origin: {origin}", flush=True)
    print("  1. GET /health (retries while Render wakes)", flush=True)

    try:
        body = wait_health(origin)
        print(json.dumps(body, indent=2), flush=True)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: deployed backend is reachable")
    print(f"  inspect: {origin}/health")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
