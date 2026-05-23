from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import numpy as np

from config.types import TripRecorderConfig

from netrapi.exceptions import RecordingError
from netrapi.recording.util.video_encode import write_h264_mp4


class TripRecorder:
    def __init__(self, config: TripRecorderConfig) -> None:
        self._config = config
        self._trip_started_at: datetime | None = None
        self._segment_started_at: float | None = None
        self._segment_index = 0
        self._segment_frames: list[np.ndarray] = []
        self._frame_size: tuple[int, int] | None = None
        self._current_path: Path | None = None
        self._active = False

    @property
    def config(self) -> TripRecorderConfig:
        return self._config

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def is_started(self) -> bool:
        return self._active

    def start(self, *, frame_shape: tuple[int, ...]) -> None:
        if len(frame_shape) < 2:
            raise RecordingError(f"trip recorder frame shape must have at least 2 dimensions, got {frame_shape}")

        height, width = frame_shape[:2]
        self.stop()

        self._frame_size = (int(width), int(height))
        self._trip_started_at = datetime.now()
        self._segment_index = 0
        self._active = True
        self._open_new_segment()

    def append_frame(self, display_frame: np.ndarray) -> None:
        if not self._active:
            raise RecordingError("trip recorder has not been started")

        now = time.monotonic()
        self._rotate_if_needed(now)
        self._segment_frames.append(np.asarray(display_frame).copy())

    def stop(self) -> None:
        if self._active and self._segment_frames:
            self._finalize_segment()
        self._active = False
        self._segment_started_at = None
        self._trip_started_at = None
        self._segment_index = 0
        self._segment_frames = []
        self._frame_size = None
        self._current_path = None

    def _rotate_if_needed(self, now: float) -> None:
        if self._segment_started_at is None:
            return
        if (now - self._segment_started_at) < self._config.segment_seconds:
            return
        self._finalize_segment()
        self._open_new_segment()

    def _open_new_segment(self) -> None:
        if self._frame_size is None or self._trip_started_at is None:
            raise RecordingError("trip recorder is missing start metadata")

        output_dir = self._config.segments_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        self._current_path = self._segment_path()
        self._segment_started_at = time.monotonic()
        self._segment_frames = []
        self._segment_index += 1
        print(
            f"[trip] segment {self._segment_index:04d} buffering "
            f"(target {self._config.segment_seconds}s wall) -> {self._current_path.name}",
            flush=True,
        )

    def _finalize_segment(self) -> None:
        output_path = self._current_path
        if output_path is None or self._segment_started_at is None:
            return

        frames = self._segment_frames
        frame_count = len(frames)
        elapsed = time.monotonic() - self._segment_started_at
        if frame_count < 2:
            raise RecordingError(
                f"trip segment {self._segment_index:04d} has {frame_count} frames; need at least 2 to encode"
            )
        if elapsed <= 0:
            raise RecordingError(f"trip segment {self._segment_index:04d} has non-positive wall elapsed {elapsed}")

        fps = frame_count / elapsed
        write_h264_mp4(
            frames=frames,
            fps=fps,
            output_path=output_path,
            crf=self._config.ffmpeg_crf,
        )
        print(
            f"[trip] segment saved: {output_path.name} | {elapsed:.1f}s wall | "
            f"{frame_count} frames | {fps:.2f} fps",
            flush=True,
        )
        self._segment_frames = []
        self._current_path = None
        self._segment_started_at = None

    def _segment_path(self) -> Path:
        if self._trip_started_at is None:
            raise RecordingError("trip recorder has not started")
        stamp = self._trip_started_at.strftime("%Y%m%d_%H%M%S")
        return self._config.segments_dir / f"trip_{stamp}_seg_{self._segment_index + 1:04d}.mp4"
