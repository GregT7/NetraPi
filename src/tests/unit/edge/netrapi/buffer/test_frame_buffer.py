from pathlib import Path

import numpy as np
import pytest

from config.types import DisplayConfig, RecordingManagerConfig
from netrapi.buffer import FrameBuffer, FrameRecord
from netrapi.exceptions import BufferError


def _recording_manager_config() -> RecordingManagerConfig:
    return RecordingManagerConfig(
        clips_dir=Path("clips"),
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        coverage_tolerance=0.95,
        display=DisplayConfig(contrast=1.0, tone_enabled=False, tone_brightness=10.0),
        record_safe_events=False,
        ffmpeg_crf=20,
    )


def _record(value: int) -> FrameRecord:
    raw = np.full((2, 2, 3), value, dtype=np.uint8)
    display = np.full((2, 2, 3), value + 100, dtype=np.uint8)
    return FrameRecord(raw=raw, display=display)


def test_pre_buffer_push_evicts_old_records():
    buffer = FrameBuffer(_recording_manager_config())
    buffer.push(_record(1), captured_at=0.0)
    buffer.push(_record(2), captured_at=1.9)
    buffer.push(_record(3), captured_at=3.5)

    frames = buffer.display_frames()
    assert [frame[0, 0, 0] for frame in frames] == [102, 103]


def test_display_frames_return_display_not_raw():
    buffer = FrameBuffer(_recording_manager_config())
    buffer.push(_record(5), captured_at=1.0)

    display_frames = buffer.display_frames()
    assert display_frames[0][0, 0, 0] == 105
    assert display_frames[0][0, 0, 0] != buffer.latest().raw[0, 0, 0]


def test_post_buffer_append_does_not_evict():
    buffer = FrameBuffer()
    buffer.append(_record(1), captured_at=0.0)
    buffer.append(_record(2), captured_at=100.0)

    assert len(buffer) == 2
    assert [frame[0, 0, 0] for frame in buffer.display_frames()] == [101, 102]


def test_capture_span_returns_count_and_times():
    buffer = FrameBuffer()
    buffer.append(_record(1), captured_at=1.0)
    buffer.append(_record(2), captured_at=2.5)

    assert buffer.capture_span() == (2, 1.0, 2.5)


def test_capture_span_empty_returns_none():
    buffer = FrameBuffer()
    assert buffer.capture_span() is None


def test_latest_and_clear():
    buffer = FrameBuffer()
    buffer.append(_record(9), captured_at=1.0)

    assert buffer.latest().raw[0, 0, 0] == 9
    buffer.clear()
    assert len(buffer) == 0


def test_push_without_recording_manager_config_raises():
    buffer = FrameBuffer()
    with pytest.raises(BufferError, match="push\\(\\) requires RecordingManagerConfig"):
        buffer.push(_record(1))


def test_latest_on_empty_buffer_raises():
    buffer = FrameBuffer()
    with pytest.raises(BufferError, match="buffer is empty"):
        buffer.latest()
