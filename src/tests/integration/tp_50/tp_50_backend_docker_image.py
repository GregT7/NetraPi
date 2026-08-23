"""
TP-50: Backend Docker image build (integration).

Builds the production Dockerfile, runs a container, GET /health.
Uses sqlite + a dummy API key so the image can boot without Render env.
Stops the container afterward. Leaves the image tagged netrapi-backend:tp50.

Usage (from repo root, Docker Desktop running):

    python src/tests/integration/tp_50/tp_50_backend_docker_image.py
"""

from __future__ import annotations

import json
import socket
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
DOCKERFILE = BACKEND_DIR / "Dockerfile"
CONTEXT = BACKEND_DIR.parent
IMAGE = "netrapi-backend:tp50"
CONTAINER = "netrapi-tp50"
WAIT_SECONDS = 90


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def _wait_health(url: str) -> dict:
    deadline = time.time() + WAIT_SECONDS
    last_error = "no attempt"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
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
    print("TP-50: Backend Docker image build", flush=True)
    print(f"  dockerfile: {DOCKERFILE}", flush=True)
    print("  1. docker build", flush=True)
    print("  2. docker run (sqlite + dummy key)", flush=True)
    print("  3. GET /health", flush=True)

    if not DOCKERFILE.is_file():
        print(f"FAIL: dockerfile not found: {DOCKERFILE}", file=sys.stderr)
        return 1

    port = _free_port()
    health_url = f"http://127.0.0.1:{port}/health"
    started = False
    try:
        built = _run(
            [
                "docker",
                "build",
                "-f",
                str(DOCKERFILE),
                "-t",
                IMAGE,
                str(CONTEXT),
            ]
        )
        if built.stdout:
            print(built.stdout, end="", flush=True)
        if built.stderr:
            print(built.stderr, end="", file=sys.stderr, flush=True)

        _run(["docker", "rm", "-f", CONTAINER], check=False)
        run = _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                CONTAINER,
                "-p",
                f"{port}:8000",
                "-e",
                "DATABASE_URL=sqlite:////tmp/netrapi.db",
                "-e",
                "NETRAPI_API_KEY=tp-50-local-key",
                IMAGE,
            ]
        )
        started = True
        container_id = (run.stdout or "").strip()
        print(f"  container: {container_id[:12]} host port {port}", flush=True)

        body = _wait_health(health_url)
        print(json.dumps(body, indent=2), flush=True)
        if body.get("status") != "ok":
            raise RuntimeError(f"unexpected status: {body!r}")
        raw_time = body.get("time")
        if not isinstance(raw_time, str) or not raw_time:
            raise RuntimeError(f"missing time: {body!r}")
        datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except subprocess.CalledProcessError as exc:
        print(f"FAIL: docker {exc.returncode}", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        if started:
            logs = _run(["docker", "logs", "--tail", "40", CONTAINER], check=False)
            print(logs.stdout or logs.stderr or "", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        if started:
            logs = _run(["docker", "logs", "--tail", "40", CONTAINER], check=False)
            print(logs.stdout or logs.stderr or "", file=sys.stderr)
        return 1
    finally:
        _run(["docker", "rm", "-f", CONTAINER], check=False)

    print("PASS: production image built; container GET /health succeeded")
    print(f"  image left tagged: {IMAGE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
