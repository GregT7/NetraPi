from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from config.loader import AppConfig
from netrapi.health import KeepAlive, run_boot_health

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "config"


def _config() -> AppConfig:
    return AppConfig.load(FIXTURES_DIR)


def test_tpu_failure_aborts():
    app_config = _config()
    detector = MagicMock()
    detector.verify_tpu.return_value = False
    with (
        patch("netrapi.health.Detector", return_value=detector),
        patch("netrapi.health.StatusOverlay"),
        patch("netrapi.health.append_health_log"),
    ):
        result = run_boot_health(app_config, overlay_enabled=False)
    assert result.abort is True
    assert result.mode == "offline"


def test_no_wifi_is_offline_not_error():
    app_config = _config()
    detector = MagicMock()
    detector.verify_tpu.return_value = True
    with (
        patch("netrapi.health.Detector", return_value=detector),
        patch("netrapi.health.wifi_associated", return_value=(False, None)),
        patch("netrapi.health.StatusOverlay"),
        patch("netrapi.health.append_health_log"),
    ):
        result = run_boot_health(app_config, overlay_enabled=False)
    assert result.abort is False
    assert result.mode == "offline"
    assert result.issues[0].code == "wifi_none"
    assert result.issues[0].persist is False
    assert result.issues[0].loud is False


def test_associated_without_internet_is_loud_offline():
    app_config = _config()
    detector = MagicMock()
    detector.verify_tpu.return_value = True
    with (
        patch("netrapi.health.Detector", return_value=detector),
        patch("netrapi.health.wifi_associated", return_value=(True, "Garage")),
        patch("netrapi.health.internet_reachable", return_value=False),
        patch("netrapi.health.StatusOverlay"),
        patch("netrapi.health.append_health_log"),
    ):
        result = run_boot_health(app_config, overlay_enabled=False)
    assert result.mode == "offline"
    assert result.abort is False
    assert result.issues[0].persist is True
    assert result.issues[0].loud is True
    assert "Garage" in result.issues[0].message


def test_online_when_health_and_ready_pass():
    app_config = _config()
    detector = MagicMock()
    detector.verify_tpu.return_value = True
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
        result = run_boot_health(app_config, overlay_enabled=False)
    assert result.mode == "online"
    assert result.abort is False
    assert result.detector is detector


def test_keepalive_gives_up_after_three_failures():
    given_up: list[str] = []
    pings = [False, False, False]
    config = replace(_config().health, keepalive_interval_s=0)
    keepalive = KeepAlive(
        config,
        ping=lambda: pings.pop(0) if pings else False,
        on_give_up=given_up.append,
        sleep=lambda _seconds: None,
    )
    with patch("netrapi.health.append_health_log"):
        keepalive._run()
    assert given_up
    assert "3 times" in given_up[0]
