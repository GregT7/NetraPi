"""Per-driving-session text log + troubleshooting stats CSV (TP-08/TP-09 style)."""

from __future__ import annotations

import csv
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


def _utc_stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_internal_temp_c() -> float | None:
    thermal = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        if thermal.is_file():
            return round(int(thermal.read_text(encoding="utf-8").strip()) / 1000.0, 2)
    except (OSError, ValueError):
        pass
    vcgencmd = shutil.which("vcgencmd")
    if not vcgencmd:
        return None
    try:
        result = subprocess.run(
            [vcgencmd, "measure_temp"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode == 0 and "=" in (result.stdout or ""):
            value = result.stdout.split("=", 1)[1].replace("'C", "").strip()
            return round(float(value), 2)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def read_throttled() -> str | None:
    """Raw ``vcgencmd get_throttled`` hex (e.g. ``0x0``); None if unavailable."""
    vcgencmd = shutil.which("vcgencmd")
    if not vcgencmd:
        return None
    try:
        result = subprocess.run(
            [vcgencmd, "get_throttled"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode == 0 and "=" in (result.stdout or ""):
            return result.stdout.split("=", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def read_disk_free_gb(path: Path) -> float | None:
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / (1024**3), 3)
    except OSError:
        return None


class TripSessionLog:
    """
    One directory per driving session::

        <logs_dir>/trip_session_<id>_<YYYYMMDD_HHMMSS>/
          trip.log      # timestamped console-style lines
          stats.csv     # periodic Pi temp / throttle / disk (TP-09 style)
    """

    def __init__(
        self,
        trip_dir: Path,
        *,
        stats_interval_s: float = 15.0,
        session_id: int | None = None,
    ) -> None:
        self.trip_dir = trip_dir
        self.session_id = session_id
        self.log_path = trip_dir / "trip.log"
        self.stats_path = trip_dir / "stats.csv"
        self._stats_interval_s = max(1.0, float(stats_interval_s))
        self._started = time.monotonic()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        trip_dir.mkdir(parents=True, exist_ok=True)
        with self.stats_path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(
                [
                    "timestamp",
                    "elapsed_sec",
                    "internal_temp_c",
                    "throttled",
                    "disk_free_gb",
                ]
            )
        self.write(
            f"trip log opened session_id={session_id} dir={trip_dir}"
        )
        self._thread = threading.Thread(
            target=self._stats_loop,
            name="trip-stats",
            daemon=True,
        )
        self._thread.start()

    @classmethod
    def open(
        cls,
        logs_dir: Path,
        *,
        session_id: int | None,
        stats_interval_s: float = 15.0,
        started_at: datetime | None = None,
    ) -> TripSessionLog:
        wall = started_at or datetime.now()
        stamp = wall.strftime("%Y%m%d_%H%M%S")
        sid = session_id if session_id is not None else 0
        trip_dir = logs_dir / f"trip_session_{sid}_{stamp}"
        return cls(
            trip_dir,
            stats_interval_s=stats_interval_s,
            session_id=session_id,
        )

    def write(self, message: str) -> None:
        line = f"{_utc_stamp()} {message}"
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        print(message, flush=True)

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self._stats_interval_s + 2.0)
        self._thread = None
        self.write("trip log closed")

    def _stats_loop(self) -> None:
        self._write_stats_row()
        while not self._stop.wait(self._stats_interval_s):
            self._write_stats_row()

    def _write_stats_row(self) -> None:
        elapsed = round(time.monotonic() - self._started, 1)
        temp = read_internal_temp_c()
        throttled = read_throttled()
        disk = read_disk_free_gb(self.trip_dir)
        row = [
            _utc_stamp(),
            elapsed,
            "" if temp is None else temp,
            throttled or "",
            "" if disk is None else disk,
        ]
        with self._lock:
            with self.stats_path.open("a", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow(row)
