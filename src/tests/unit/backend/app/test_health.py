from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from app.routes.health import health


def test_health_status_ok_and_utc_z() -> None:
    frozen = datetime(2026, 8, 20, 13, 30, 0, tzinfo=timezone.utc)
    with patch("app.routes.health.datetime") as mock_datetime:
        mock_datetime.now.return_value = frozen
        body = health()
    assert body == {"status": "ok", "time": "2026-08-20T13:30:00Z"}
    mock_datetime.now.assert_called_once_with(timezone.utc)
