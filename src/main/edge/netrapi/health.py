from __future__ import annotations

import json
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

from config.loader import AppConfig
from config.types import HealthConfig, PreviewConfig
from netrapi.capture import PreviewUI
from netrapi.detection import Detector
from netrapi.exceptions import DetectionError, IngestAuthError

Mode = Literal["online", "offline"]

EDGE_DIR = Path(__file__).resolve().parents[1]


@dataclass
class HealthIssue:
    code: str
    message: str
    persist: bool = False
    loud: bool = False


@dataclass
class HealthResult:
    mode: Mode
    abort: bool
    detector: Detector | None
    issues: list[HealthIssue] = field(default_factory=list)

    @property
    def persist_messages(self) -> list[str]:
        return [issue.message for issue in self.issues if issue.persist]


class StatusOverlay:
    def __init__(self, preview: PreviewConfig, *, enabled: bool = True) -> None:
        self._ui: PreviewUI | None = None
        if enabled:
            try:
                self._ui = PreviewUI(replace(preview, enabled=True))
            except Exception:
                self._ui = None

    def update(self, lines: list[str]) -> None:
        for line in lines:
            print(line, flush=True)
        if self._ui is None:
            return
        try:
            self._ui.show(_status_frame(lines, self._ui.config))
        except Exception:
            pass


def _status_frame(lines: list[str], preview: PreviewConfig) -> np.ndarray:
    height = max(240, min(preview.max_height, 480))
    width = max(320, min(preview.max_width, 854))
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (32, 24, 8)
    try:
        import cv2
    except ImportError:
        return frame
    y = 36
    cv2.putText(
        frame,
        "NetraPi boot health",
        (16, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (240, 240, 240),
        2,
        cv2.LINE_AA,
    )
    y += 32
    for line in lines:
        cv2.putText(
            frame,
            line[:80],
            (16, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )
        y += 24
        if y > height - 16:
            break
    return frame


def _log_path(config: HealthConfig) -> Path:
    path = config.log_path
    if not path.is_absolute():
        path = EDGE_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_health_log(config: HealthConfig, message: str) -> None:
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with _log_path(config).open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} {message}\n")


def wifi_associated(interface: str) -> tuple[bool, str | None]:
    try:
        completed = subprocess.run(
            ["iwgetid", "-r"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        ssid = (completed.stdout or "").strip()
        if completed.returncode == 0 and ssid:
            return True, ssid
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        pass
    operstate = Path(f"/sys/class/net/{interface}/operstate")
    try:
        if operstate.read_text(encoding="utf-8").strip() == "up":
            return True, interface
    except OSError:
        pass
    return False, None


def internet_reachable(config: HealthConfig) -> bool:
    try:
        socket.create_connection(
            (config.internet_probe_host, config.internet_probe_port),
            timeout=config.internet_probe_timeout_s,
        ).close()
    except OSError:
        return False
    try:
        socket.create_connection(
            (config.public_https_host, config.public_https_port),
            timeout=config.internet_probe_timeout_s,
        ).close()
    except OSError:
        return False
    return True


def _get_url(
    url: str, *, timeout_s: float, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, Any] | None]:
    request = urllib.request.Request(url, method="GET", headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
            status = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = int(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, None
    if not raw:
        return status, {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return status, None
    if not isinstance(parsed, dict):
        return status, None
    return status, parsed


def poll_render_health(
    config: HealthConfig, base_url: str, overlay: StatusOverlay | None = None
) -> bool:
    url = base_url.rstrip("/") + "/health"
    deadline = time.monotonic() + config.render_wait_s
    started = time.monotonic()
    while time.monotonic() < deadline:
        elapsed = int(time.monotonic() - started)
        if overlay is not None:
            overlay.update(
                [
                    f"Render: waiting {elapsed}/{int(config.render_wait_s)}s",
                    "waking Render...",
                ]
            )
        status, body = _get_url(url, timeout_s=config.render_request_timeout_s)
        if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(config.render_poll_s, remaining))
    return False


def check_ready(
    config: HealthConfig, base_url: str, headers: dict[str, str]
) -> tuple[bool, str]:
    url = base_url.rstrip("/") + "/api/netrapi/ready"
    status, body = _get_url(
        url, timeout_s=config.render_request_timeout_s, headers=headers
    )
    if status == 200 and isinstance(body, dict) and body.get("status") == "ok":
        return True, "ready ok"
    if isinstance(body, dict):
        detail = f"database={body.get('database')} s3={body.get('s3')}"
        extra = body.get("detail")
        if extra:
            detail = f"{detail} detail={extra}"
        return False, detail
    if status == 0:
        return False, "no response"
    return False, f"HTTP {status}"


def run_boot_health(app_config: AppConfig, *, overlay_enabled: bool = True) -> HealthResult:
    health = app_config.health
    overlay = StatusOverlay(app_config.preview, enabled=overlay_enabled)
    issues: list[HealthIssue] = []

    def note(issue: HealthIssue) -> None:
        issues.append(issue)
        prefix = "ERROR" if issue.loud or issue.code == "tpu" else "INFO"
        append_health_log(health, f"{prefix} {issue.code}: {issue.message}")
        if issue.loud:
            print(f"[health] {issue.message}", flush=True)

    overlay.update(["TPU: checking..."])
    detector: Detector | None = None
    try:
        detector = Detector(app_config.detector)
        detector.load()
        if not detector.verify_tpu():
            note(
                HealthIssue(
                    "tpu",
                    "Coral USB TPU smoke check failed. Reseat the Coral and rerun.",
                    persist=False,
                    loud=True,
                )
            )
            overlay.update(["TPU: fail", "Mode: abort"])
            return HealthResult(mode="offline", abort=True, detector=detector, issues=issues)
    except DetectionError as exc:
        note(HealthIssue("tpu", str(exc), persist=False, loud=True))
        overlay.update(["TPU: fail", "Mode: abort"])
        return HealthResult(mode="offline", abort=True, detector=None, issues=issues)

    overlay.update(["TPU: pass", "Wi-Fi: checking..."])
    associated, ssid = wifi_associated(health.wlan_interface)
    if not associated:
        note(
            HealthIssue(
                "wifi_none",
                "No Wi-Fi association; starting offline.",
                persist=False,
                loud=False,
            )
        )
        overlay.update(["TPU: pass", "Wi-Fi: not associated", "Mode: OFFLINE"])
        return HealthResult(mode="offline", abort=False, detector=detector, issues=issues)

    label = ssid or health.wlan_interface
    overlay.update(
        ["TPU: pass", f"Wi-Fi: associated ({label})", "Internet: checking..."]
    )
    if not internet_reachable(health):
        message = (
            f"Wi-Fi associated ({label}) but internet unreachable "
            f"({health.internet_probe_host}:{health.internet_probe_port} / "
            f"{health.public_https_host}:{health.public_https_port}). Starting offline."
        )
        note(HealthIssue("wifi_no_internet", message, persist=True, loud=True))
        overlay.update(
            [
                "TPU: pass",
                f"Wi-Fi: associated ({label}) / no internet",
                "Mode: OFFLINE",
            ]
        )
        return HealthResult(mode="offline", abort=False, detector=detector, issues=issues)

    from netrapi.backend_auth import ingest_api_url, ingest_headers, load_ingest_auth

    try:
        load_ingest_auth()
        base_url = ingest_api_url()
        headers = ingest_headers()
    except IngestAuthError as exc:
        message = f"Internet up but ingest auth missing ({exc}). Starting offline."
        note(HealthIssue("auth", message, persist=True, loud=True))
        overlay.update(
            [
                "TPU: pass",
                f"Wi-Fi: associated ({label})",
                "Cloud: auth missing",
                "Mode: OFFLINE",
            ]
        )
        return HealthResult(mode="offline", abort=False, detector=detector, issues=issues)

    overlay.update(
        ["TPU: pass", f"Wi-Fi: associated ({label})", "Render: waking..."]
    )
    if not poll_render_health(health, base_url, overlay):
        message = (
            f"Render GET /health did not succeed within {int(health.render_wait_s)}s. "
            "Starting offline."
        )
        note(HealthIssue("render", message, persist=True, loud=True))
        overlay.update(
            [
                "TPU: pass",
                f"Wi-Fi: associated ({label})",
                "Render: timeout",
                "Mode: OFFLINE",
            ]
        )
        return HealthResult(mode="offline", abort=False, detector=detector, issues=issues)

    overlay.update(
        [
            "TPU: pass",
            f"Wi-Fi: associated ({label})",
            "Render: up",
            "Ready: checking...",
        ]
    )
    ready_ok, ready_detail = check_ready(health, base_url, headers)
    if not ready_ok:
        message = f"GET /api/netrapi/ready failed ({ready_detail}). Starting offline."
        note(HealthIssue("ready", message, persist=True, loud=True))
        overlay.update(
            [
                "TPU: pass",
                f"Wi-Fi: associated ({label})",
                f"Ready: fail ({ready_detail})",
                "Mode: OFFLINE",
            ]
        )
        return HealthResult(mode="offline", abort=False, detector=detector, issues=issues)

    overlay.update(
        [
            "TPU: pass",
            f"Wi-Fi: associated ({label})",
            "Render: up",
            "Ready: ok",
            "Mode: ONLINE",
        ]
    )
    append_health_log(health, "INFO boot online")
    return HealthResult(mode="online", abort=False, detector=detector, issues=issues)


def wake_render(app_config: AppConfig) -> bool:
    from netrapi.backend_auth import ingest_api_url, load_ingest_auth

    load_ingest_auth()
    return poll_render_health(app_config.health, ingest_api_url(), overlay=None)


class KeepAlive:
    def __init__(
        self,
        config: HealthConfig,
        *,
        ping: Callable[[], bool] | None = None,
        on_give_up: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._ping = ping or self._default_ping
        self._on_give_up = on_give_up
        self._sleep = sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._failures = 0

    def _default_ping(self) -> bool:
        from netrapi.backend_auth import ingest_api_url

        url = ingest_api_url().rstrip("/") + "/health"
        status, body = _get_url(url, timeout_s=self._config.keepalive_request_timeout_s)
        return status == 200 and isinstance(body, dict) and body.get("status") == "ok"

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="netrapi-keepalive", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2)
        self._thread = None

    def _run(self) -> None:
        interval = self._config.keepalive_interval_s
        while not self._stop.wait(interval):
            try:
                ok = self._ping()
            except Exception as exc:
                ok = False
                append_health_log(self._config, f"ERROR keepalive: {exc}")
            if ok:
                self._failures = 0
                continue
            self._failures += 1
            append_health_log(
                self._config,
                f"ERROR keepalive fail {self._failures}/{self._config.keepalive_fail_limit}",
            )
            print(
                f"[health] keep-alive GET /health failed ({self._failures}/"
                f"{self._config.keepalive_fail_limit})",
                flush=True,
            )
            if self._failures >= self._config.keepalive_fail_limit:
                reason = (
                    f"Keep-alive GET /health failed {self._failures} times in a row; "
                    "dropping to offline for the rest of this process."
                )
                append_health_log(self._config, f"ERROR {reason}")
                if self._on_give_up is not None:
                    self._on_give_up(reason)
                return
