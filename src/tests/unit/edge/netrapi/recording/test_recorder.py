from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from config.types import DisplayConfig, RecordingManagerConfig
from netrapi.exceptions import RecordingError
from netrapi.recording import ClipPackage, Recorder


def _recording_manager_config(tmp_path: Path) -> RecordingManagerConfig:
    return RecordingManagerConfig(
        clips_dir=tmp_path / "clips",
        pre_roll_seconds=10.0,
        post_roll_seconds=10.0,
        coverage_tolerance=0.95,
        display=DisplayConfig(contrast=1.0, tone_enabled=False, tone_brightness=10.0),
        record_safe_events=False,
        ffmpeg_crf=20,
    )


def test_write_clip_encodes_pre_then_post(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    package = ClipPackage.build(
        [frame, frame],
        [frame],
        triggered_at=datetime(2026, 5, 1, 12, 0, 0),
        event_index=1,
    )
    recorder = Recorder(_recording_manager_config(tmp_path))

    with patch("netrapi.recording.recorder.write_h264_mp4") as encode:
        result = recorder.write_clip(package, fps=29.5)

    assert result.pre_frame_count == 2
    assert result.post_frame_count == 1
    assert result.clip_path.parent.parent == tmp_path / "clips"
    assert result.clip_path.name == "clip.mp4"
    assert result.clip_path.parent.name.startswith("clip_1_")
    encode.assert_called_once()
    assert encode.call_args.kwargs["fps"] == pytest.approx(29.5)
    assert len(encode.call_args.kwargs["frames"]) == 3


def test_write_clip_empty_package_raises(tmp_path: Path):
    recorder = Recorder(_recording_manager_config(tmp_path))
    package = ClipPackage.build([], [], event_index=1)

    with pytest.raises(RecordingError, match="no frames"):
        recorder.write_clip(package, fps=30.0)


def test_write_clip_rejects_non_positive_fps(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    package = ClipPackage.build([frame], [frame], event_index=1)
    recorder = Recorder(_recording_manager_config(tmp_path))

    with pytest.raises(RecordingError, match="greater than 0"):
        recorder.write_clip(package, fps=0.0)


def test_clip_result_pre_and_post_ok_flags(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    recording_manager_config = RecordingManagerConfig(
        clips_dir=tmp_path / "clips",
        pre_roll_seconds=0.1,
        post_roll_seconds=0.1,
        coverage_tolerance=0.95,
        display=DisplayConfig(contrast=1.0, tone_enabled=False, tone_brightness=10.0),
        record_safe_events=False,
        ffmpeg_crf=20,
    )
    package = ClipPackage.build([frame] * 10, [frame] * 10, event_index=1)
    recorder = Recorder(recording_manager_config)

    with patch("netrapi.recording.recorder.write_h264_mp4"):
        result = recorder.write_clip(package, fps=30.0)

    assert result.pre_ok is True
    assert result.post_ok is True
    assert result.notes == ""
