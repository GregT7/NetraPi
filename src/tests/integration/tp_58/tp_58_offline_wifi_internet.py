"""
TP-58: Offline when Wi-Fi is missing or internet fails (integration).

Mocks TPU pass plus (1) no association and (2) associated but no internet.
Capture would still start; cloud ingest stays off.
"""

from __future__ import annotations

import sys
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
    from netrapi.health import HealthResult, run_boot_health

    print("TP-58: Offline when Wi-Fi is missing or internet fails", flush=True)
    app_config = _config()
    detector = MagicMock()
    detector.verify_tpu.return_value = True

    print("  1. TPU pass + no Wi-Fi association", flush=True)
    with (
        patch("netrapi.health.Detector", return_value=detector),
        patch("netrapi.health.wifi_associated", return_value=(False, None)),
        patch("netrapi.health.StatusOverlay"),
        patch("netrapi.health.append_health_log"),
    ):
        none = run_boot_health(app_config, overlay_enabled=False)
    if none.abort or none.mode != "offline":
        raise RuntimeError(f"no-wifi should be offline capture, got {none}")
    if none.issues[0].code != "wifi_none" or none.issues[0].persist or none.issues[0].loud:
        raise RuntimeError(f"no-wifi issue should be informational: {none.issues[0]}")

    print("  2. TPU pass + associated + no internet", flush=True)
    with (
        patch("netrapi.health.Detector", return_value=detector),
        patch("netrapi.health.wifi_associated", return_value=(True, "Garage")),
        patch("netrapi.health.internet_reachable", return_value=False),
        patch("netrapi.health.StatusOverlay"),
        patch("netrapi.health.append_health_log"),
    ):
        loud = run_boot_health(app_config, overlay_enabled=False)
    if loud.abort or loud.mode != "offline":
        raise RuntimeError(f"no-internet should be offline capture, got {loud}")
    if not loud.issues[0].persist or not loud.issues[0].loud:
        raise RuntimeError("associated-no-internet should persist a loud log")
    if "Garage" not in loud.issues[0].message:
        raise RuntimeError(f"loud log should name the SSID: {loud.issues[0].message}")

    print("  3. Offline main() still starts capture without keep-alive", flush=True)
    pipeline = MagicMock()
    health = HealthResult(mode="offline", abort=False, detector=detector)
    with (
        patch("config.loader.AppConfig.load", return_value=MagicMock()),
        patch("db.database.init_engine"),
        patch("netrapi.build_pipeline", return_value=pipeline) as build,
        patch("netrapi.backend_auth.apply_edge_env"),
        patch("netrapi.health.run_boot_health", return_value=health),
        patch("netrapi.health.KeepAlive") as keepalive_cls,
        patch("main._resolve_runtime_paths", side_effect=lambda cfg, _root: cfg),
    ):
        code = edge_main([])
    if code != 0:
        raise RuntimeError(f"offline capture should exit 0, got {code}")
    if build.call_args.kwargs.get("cloud_enabled") is not False:
        raise RuntimeError("offline capture must set cloud_enabled=False")
    if keepalive_cls.called:
        raise RuntimeError("KeepAlive should not start offline")
    pipeline.run.assert_called_once()
    print("PASS: missing Wi-Fi / no internet start offline capture", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
