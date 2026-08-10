import pytest

from netrapi.exceptions import RecordingError
from netrapi.recording.util.encoding_fps import clip_encoding_fps, encoding_fps


def test_encoding_fps_from_span():
    assert encoding_fps(frame_count=31, first_at=0.0, last_at=1.0) == pytest.approx(31.0)


def test_encoding_fps_rejects_single_frame():
    with pytest.raises(RecordingError, match="at least 2 frames"):
        encoding_fps(frame_count=1, first_at=0.0, last_at=1.0)


def test_encoding_fps_rejects_zero_elapsed():
    with pytest.raises(RecordingError, match="positive"):
        encoding_fps(frame_count=3, first_at=1.0, last_at=1.0)


def test_clip_encoding_fps_combines_pre_and_post_spans():
    pre = (11, 0.0, 1.0)
    post = (6, 1.0, 1.5)
    assert clip_encoding_fps(pre, post) == pytest.approx(17 / 1.5)


def test_clip_encoding_fps_requires_spans():
    with pytest.raises(RecordingError, match="no capture timestamps"):
        clip_encoding_fps(None, None)
