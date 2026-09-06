from __future__ import annotations

import csv
import time
from pathlib import Path

from netrapi.trip_log import TripSessionLog


def test_trip_session_log_writes_text_and_stats(tmp_path: Path) -> None:
    log = TripSessionLog.open(
        tmp_path / "logs",
        session_id=42,
        stats_interval_s=1.0,
    )
    try:
        log.write("[trip] hello")
        time.sleep(1.2)
    finally:
        log.close()

    assert log.trip_dir.is_dir()
    assert log.trip_dir.name.startswith("trip_session_42_")
    text = log.log_path.read_text(encoding="utf-8")
    assert "[trip] hello" in text
    assert "trip log opened" in text
    assert "trip log closed" in text

    with log.stats_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert "timestamp" in rows[0]
    assert "internal_temp_c" in rows[0]
    assert "throttled" in rows[0]
    assert "disk_free_gb" in rows[0]
