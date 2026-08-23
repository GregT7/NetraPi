from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from config.types import TripRecorderConfig
from netrapi.exceptions import RecordingError
from netrapi.recording.trip_recorder import TripRecorder


def _trip_config(tmp_path: Path, *, segment_seconds: int = 300) -> TripRecorderConfig:
    return TripRecorderConfig(
        enabled=True,
        segments_dir=tmp_path / "trips",
        segment_seconds=segment_seconds,
        ffmpeg_crf=20,
    )


def test_start_buffers_frames_without_encoding(tmp_path: Path) -> None:
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    recorder = TripRecorder(_trip_config(tmp_path))

    with patch("netrapi.recording.trip_recorder.write_h264_mp4") as encode:
        recorder.start(frame_shape=frame.shape)
        recorder.append_frame(frame)
        recorder.append_frame(frame + 1)

    assert recorder.is_started is True
    assert len(recorder._segment_frames) == 2
    encode.assert_not_called()


def test_finalize_on_rotate_uses_frame_count_and_elapsed(tmp_path: Path) -> None:
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    recorder = TripRecorder(_trip_config(tmp_path, segment_seconds=1))

    with patch("netrapi.recording.trip_recorder.write_h264_mp4") as encode:
        with patch("netrapi.recording.trip_recorder.time.monotonic", side_effect=[8.0, 8.2, 8.5, 9.1, 9.5, 9.5]):
            recorder.start(frame_shape=frame.shape)
            recorder.append_frame(frame)
            recorder.append_frame(frame)
            recorder.append_frame(frame)

    encode.assert_called_once()
    assert encode.call_args.kwargs["fps"] == pytest.approx(2 / 1.5)
    assert len(recorder._segment_frames) == 1


def test_stop_invokes_on_segment_saved(tmp_path: Path) -> None:
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    callback = MagicMock()
    recorder = TripRecorder(_trip_config(tmp_path), on_segment_saved=callback)

    with patch("netrapi.recording.trip_recorder.write_h264_mp4"):
        with patch("netrapi.recording.trip_recorder.time.monotonic", side_effect=[0.0, 0.0, 1.0, 2.0]):
            recorder.start(frame_shape=frame.shape)
            recorder.append_frame(frame)
            recorder.append_frame(frame)
            recorder.stop()

    callback.assert_called_once()
    kwargs = callback.call_args.kwargs
    assert kwargs["order_number"] == 1
    assert kwargs["local_path"].name.endswith("_seg_0001.mp4")


def test_stop_finalizes_open_segment(tmp_path: Path) -> None:
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    recorder = TripRecorder(_trip_config(tmp_path))

    with patch("netrapi.recording.trip_recorder.write_h264_mp4") as encode:
        with patch("netrapi.recording.trip_recorder.time.monotonic", side_effect=[0.0, 0.0, 1.0, 2.0]):
            recorder.start(frame_shape=frame.shape)
            recorder.append_frame(frame)
            recorder.append_frame(frame)
            recorder.stop()

    encode.assert_called_once()
    assert recorder.is_started is False


def test_finalize_rejects_single_frame_segment(tmp_path: Path) -> None:
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    recorder = TripRecorder(_trip_config(tmp_path))

    recorder.start(frame_shape=frame.shape)
    recorder.append_frame(frame)

    with pytest.raises(RecordingError, match="at least 2"):
        recorder.stop()
