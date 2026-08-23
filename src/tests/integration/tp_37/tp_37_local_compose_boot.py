"""
TP-37: Local backend boots via Docker Compose (integration).

Builds and starts src/main/backend/compose.yml, GET /health, prints JSON.
Leaves the stack running (docker compose down from that directory to stop).

Usage (from repo root, Docker Desktop running):

    python src/tests/integration/tp_37/tp_37_local_compose_boot.py

Compose overrides DATABASE_URL to sqlite inside the container.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
BACKEND_DIR = REPO_ROOT / "src" / "main" / "backend"
COMPOSE_FILE = BACKEND_DIR / "compose.yml"
HEALTH_URL = "http://127.0.0.1:8000/health"
WAIT_SECONDS = 90


def _compose(*args: str) -> subprocess.CompletedProcess[str]:
    if not COMPOSE_FILE.is_file():
        raise RuntimeError(f"compose file not found: {COMPOSE_FILE}")
    return subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        cwd=BACKEND_DIR,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def _wait_health() -> dict:
    deadline = time.time() + WAIT_SECONDS
    last_error = "no attempt"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
                if response.status != 200:
                    last_error = f"HTTP {response.status}"
                    time.sleep(2)
                    continue
                body = json.loads(response.read().decode("utf-8"))
                return body
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2)
    raise RuntimeError(f"GET /health did not succeed within {WAIT_SECONDS}s: {last_error}")


def main() -> int:
    print("TP-37: Local backend boots via Docker Compose", flush=True)
    print(f"  compose: {COMPOSE_FILE}", flush=True)
    print("  1. docker compose up --build -d", flush=True)
    print("  2. GET /health", flush=True)

    try:
        built = _compose("up", "--build", "-d")
        if built.stdout:
            print(built.stdout, end="", flush=True)
        if built.stderr:
            print(built.stderr, end="", file=sys.stderr, flush=True)
        body = _wait_health()
        print(json.dumps(body, indent=2), flush=True)
        if body.get("status") != "ok":
            raise RuntimeError(f"unexpected status: {body!r}")
        raw_time = body.get("time")
        if not isinstance(raw_time, str) or not raw_time:
            raise RuntimeError(f"missing time: {body!r}")
        datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        logs = _compose("logs", "--tail", "30", "backend")
        print(logs.stdout, end="", flush=True)
    except subprocess.CalledProcessError as exc:
        print(f"FAIL: docker compose {exc.returncode}", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("PASS: Compose backend is up; GET /health succeeded")
    print("  leave running: docker compose -f src/main/backend/compose.yml logs -f backend")
    print("  stop:          cd src/main/backend && docker compose down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
