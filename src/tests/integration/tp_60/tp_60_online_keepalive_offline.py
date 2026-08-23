"""
TP-60: Online boot and keep-alive drop to offline (integration).

Mocks a full online boot, then three failed keep-alive pings. Cloud ingest
is disabled for the rest of the process.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _render import configure_import_path  # noqa: E402

configure_import_path()

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "config"


def _config():
    from config.loader import AppConfig

    return AppConfig.load(FIXTURES_DIR)


def main() -> int:
    from main import main as edge_main
    from netrapi.health import HealthResult, KeepAlive, run_boot_health

    print("TP-60: Online boot and keep-alive drop to offline", flush=True)
    app_config = _config()
    detector = MagicMock()
    detector.verify_tpu.return_value = True

    print("  1. Association + internet + /health + /ready => online", flush=True)
    with (
        patch("netrapi.health.Detector", return_value=detector),
        patch("netrapi.health.wifi_associated", return_value=(True, "Home")),
        patch("netrapi.health.internet_reachable", return_value=True),
        patch("netrapi.health.poll_render_health", return_value=True),
        patch("netrapi.health.check_ready", return_value=(True, "ok")),
        patch("netrapi.backend_auth.load_ingest_auth"),
        patch("netrapi.backend_auth.ingest_api_url", return_value="https://example.test"),
        patch("netrapi.backend_auth.ingest_headers", return_value={"X-API-Key": "k"}),
        patch("netrapi.health.StatusOverlay"),
        patch("netrapi.health.append_health_log"),
    ):
        boot = run_boot_health(app_config, overlay_enabled=False)
    if boot.mode != "online" or boot.abort:
        raise RuntimeError(f"boot should be online, got {boot}")

    print("  2. main() wires KeepAlive and cloud ingest", flush=True)
    pipeline = MagicMock()
    health = HealthResult(mode="online", abort=False, detector=detector)
    with (
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch("db.database.init_engine"),
        patch("netrapi.build_pipeline", return_value=pipeline) as build,
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("netrapi.health.run_boot_health", return_value=health),
        patch("netrapi.health.KeepAlive") as keepalive_cls,
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        keepalive_cls.return_value = MagicMock()
        code = edge_main([])
    if code != 0:
        raise RuntimeError(f"online main should exit 0, got {code}")
    if build.call_args.kwargs.get("cloud_enabled") is not True:
        raise RuntimeError("online boot must set cloud_enabled=True")
    keepalive_cls.return_value.start.assert_called_once()
    keepalive_cls.return_value.stop.assert_called_once()

    print("  3. Three keep-alive failures disable cloud ingest", flush=True)
    given_up: list[str] = []
    pings = [False, False, False]

    class Manager:
        def __init__(self) -> None:
            self.cloud_ingest: object | None = object()

        def disable_cloud(self, reason: str) -> None:
            self.cloud_ingest = None
            given_up.append(reason)

    manager = Manager()
    keepalive = KeepAlive(
        replace(app_config.health, keepalive_interval_s=0),
        ping=lambda: pings.pop(0) if pings else False,
        on_give_up=manager.disable_cloud,
        sleep=lambda _seconds: None,
    )
    with patch("netrapi.health.append_health_log"):
        keepalive._run()
    if manager.cloud_ingest is not None:
        raise RuntimeError("cloud ingest should be None after three failures")
    if not given_up or "3 times" not in given_up[0]:
        raise RuntimeError(f"give-up reason should mention 3 failures: {given_up!r}")
    print("PASS: online boot; three keep-alive fails drop to offline", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
