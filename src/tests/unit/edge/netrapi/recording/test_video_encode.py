from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from netrapi.exceptions import RecordingError
from netrapi.recording.util.video_encode import write_h264_mp4


def _frame(value: int = 0) -> np.ndarray:
    return np.full((48, 64, 3), value, dtype=np.uint8)


def test_write_h264_mp4_pipes_frames_to_ffmpeg(tmp_path: Path) -> None:
    frames = [_frame(1), _frame(2)]
    output_path = tmp_path / "out" / "clip.mp4"
    mock_process = MagicMock()
    mock_process.stdin = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate.return_value = (b"", b"")

    with patch("netrapi.recording.util.video_encode.subprocess.Popen", return_value=mock_process) as popen:
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "stat") as stat:
                stat.return_value = MagicMock(st_size=10_000)
                write_h264_mp4(frames=frames, fps=30.0, output_path=output_path, crf=20)

    popen.assert_called_once()
    cmd = popen.call_args.args[0]
    assert "libx264" in cmd
    assert "yuv420p" in cmd
    assert str(output_path) in cmd
    assert mock_process.stdin.write.call_count == 2


def test_write_h264_mp4_requires_ffmpeg(tmp_path: Path) -> None:
    with patch(
        "netrapi.recording.util.video_encode.subprocess.Popen",
        side_effect=FileNotFoundError,
    ):
        with pytest.raises(RecordingError, match="ffmpeg not found"):
            write_h264_mp4(frames=[_frame(), _frame(2)], fps=30.0, output_path=tmp_path / "x.mp4", crf=20)


def test_write_h264_mp4_rejects_single_frame(tmp_path: Path) -> None:
    with pytest.raises(RecordingError, match="at least 2 frames"):
        write_h264_mp4(frames=[_frame()], fps=30.0, output_path=tmp_path / "x.mp4", crf=20)


def test_write_h264_mp4_ignores_flush_of_closed_file_on_stdin_close(tmp_path: Path) -> None:
    frames = [_frame(1), _frame(2)]
    output_path = tmp_path / "out" / "clip.mp4"
    mock_stdin = MagicMock()
    mock_stdin.close.side_effect = ValueError("flush of closed file")
    mock_process = MagicMock()
    mock_process.stdin = mock_stdin
    mock_process.returncode = 0

    def communicate_like_cpython(input=None, timeout=None):
        # Mirror Popen._stdin_write: close stdin again if still attached.
        if mock_process.stdin is not None:
            mock_process.stdin.close()
        return (b"", b"")

    mock_process.communicate.side_effect = communicate_like_cpython

    with patch("netrapi.recording.util.video_encode.subprocess.Popen", return_value=mock_process):
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "stat") as stat:
                stat.return_value = MagicMock(st_size=10_000)
                write_h264_mp4(frames=frames, fps=30.0, output_path=output_path, crf=20)

    mock_stdin.close.assert_called_once()
    assert mock_process.stdin is None
    mock_process.communicate.assert_called_once()
