from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.s3 import (
    media_object_key,
    month_year_stamp,
    s3_settings_or_raise,
    S3NotConfiguredError,
)
from app.config import Settings


def test_media_object_key_clip_uses_session_month() -> None:
    started = datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone.utc)
    assert (
        media_object_key(kind="clip", row_id=10, session_id=1, start_time=started)
        == "Aug-2026/driving_session_id_1/clips/clip-10.mp4"
    )


def test_media_object_key_trip_is_stable() -> None:
    started = datetime(2026, 8, 16, 18, 0, 0, tzinfo=timezone.utc)
    first = media_object_key(kind="trip", row_id=3, session_id=1, start_time=started)
    second = media_object_key(kind="trip", row_id=3, session_id=1, start_time=started)
    assert first == second == "Aug-2026/driving_session_id_1/trips/trip-3.mp4"


def test_media_object_key_naive_datetime_treated_as_utc() -> None:
    started = datetime(2026, 8, 16, 18, 0, 0)
    assert media_object_key(
        kind="clip", row_id=1, session_id=1, start_time=started
    ).startswith("Aug-2026/")


def test_month_year_stamp_uses_english_table() -> None:
    assert month_year_stamp(datetime(2026, 1, 15, tzinfo=timezone.utc)) == "Jan-2026"
    assert month_year_stamp(datetime(2026, 12, 1, tzinfo=timezone.utc)) == "Dec-2026"


def test_s3_settings_or_raise_when_missing() -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        netrapi_api_key="k",
        _env_file=None,
    )
    with pytest.raises(S3NotConfiguredError):
        s3_settings_or_raise(settings)
