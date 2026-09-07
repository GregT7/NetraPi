from __future__ import annotations

from pathlib import Path

import numpy as np

from config.types import RecordingManagerConfig

from netrapi.exceptions import RecordingError
from netrapi.recording.clip_package import ClipPackage
from netrapi.recording.clip_result import ClipResult
from netrapi.recording.util.video_encode import write_h264_mp4


class Recorder:
    def __init__(self, recording_manager_config: RecordingManagerConfig) -> None:
        self._config = recording_manager_config
        self._out_path: Path | None = None

    @property
    def recording_manager_config(self) -> RecordingManagerConfig:
        return self._config

    def write_clip(self, package: ClipPackage, *, fps: float) -> ClipResult:
        frames = list(package.pre_frames) + list(package.post_frames)
        if not frames:
            raise RecordingError("clip package has no frames to write")
        if fps <= 0:
            raise RecordingError(f"fps must be greater than 0, got {fps}")

        self._out_path = self._clip_path_for(package)
        clip_path = self._out_path
        try:
            write_h264_mp4(
                frames=[np.asarray(frame) for frame in frames],
                fps=float(fps),
                output_path=clip_path,
                crf=self._config.ffmpeg_crf,
            )
        except Exception as exc:
            raise RecordingError(f"failed while writing {clip_path}: {exc}") from exc

        pre_count = len(package.pre_frames)
        post_count = len(package.post_frames)
        pre_ok, post_ok, notes = self._evaluate_coverage(
            pre_count=pre_count,
            post_count=post_count,
            fps=fps,
        )

        return ClipResult(
            clip_path=clip_path,
            pre_frame_count=pre_count,
            post_frame_count=post_count,
            pre_ok=pre_ok,
            post_ok=post_ok,
            notes=notes,
        )

    def _evaluate_coverage(
        self, *, pre_count: int, post_count: int, fps: float
    ) -> tuple[bool, bool, str]:
        tolerance = self._config.coverage_tolerance
        pre_ok = (pre_count / fps) >= self._config.pre_roll_seconds * tolerance
        post_ok = (post_count / fps) >= self._config.post_roll_seconds * tolerance

        notes: list[str] = []
        if not pre_ok:
            notes.append("pre-event coverage below target")
        if not post_ok:
            notes.append("post-event coverage below target")
        return pre_ok, post_ok, "; ".join(notes)

    def _clip_path_for(self, package: ClipPackage) -> Path:
        output_dir = self._config.clips_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = package.triggered_at.strftime("%Y%m%d_%H%M%S")
        clip_dir = output_dir / f"clip_{package.event_index}_{stamp}"
        return clip_dir / "clip.mp4"

    def release(self) -> None:
        self._out_path = None
