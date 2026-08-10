from __future__ import annotations

import time
from collections import deque
from typing import Deque

from config.types import RecordingManagerConfig

from netrapi.buffer.frame_record import FrameRecord
from netrapi.exceptions import BufferError


class FrameBuffer:
    """Rolling pre-roll deque or append-only post-roll storage of FrameRecord entries."""

    def __init__(self, recording_manager_config: RecordingManagerConfig | None = None) -> None:
        self._recording_manager_config = recording_manager_config
        self._records: Deque[tuple[float, FrameRecord]] = deque()

    # push is for pre-roll buffer
    # it evicts the oldest frames to maintain the pre-roll buffer size
    def push(self, record: FrameRecord, *, captured_at: float | None = None) -> None:
        if self._recording_manager_config is None:
            raise BufferError("push() requires RecordingManagerConfig (pre_buffer only)")

        timestamp = time.monotonic() if captured_at is None else captured_at
        self._records.append((timestamp, record))
        self._evict_before(timestamp - self._recording_manager_config.pre_roll_seconds)

    # append is for post-roll buffer
    # it simply appends the frames to the buffer
    def append(self, record: FrameRecord, *, captured_at: float | None = None) -> None:
        timestamp = time.monotonic() if captured_at is None else captured_at
        self._records.append((timestamp, record))

    def latest(self) -> FrameRecord:
        if not self._records:
            raise BufferError("buffer is empty")
        return self._records[-1][1]

    def display_frames(self) -> list:
        """Return display frames oldest → newest (for ClipPackage / MP4; not raw)."""
        return [record.display for _, record in self._records]

    def capture_span(self) -> tuple[int, float, float] | None:
        """Frame count and monotonic capture times for oldest/newest entries."""
        if not self._records:
            return None
        return len(self._records), self._records[0][0], self._records[-1][0]

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)

    def _evict_before(self, cutoff: float) -> None:
        while self._records and self._records[0][0] < cutoff:
            self._records.popleft()
