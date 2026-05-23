from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from config.types import CameraConfig
from netrapi.capture import Camera
from netrapi.exceptions import CameraError


def _camera_config() -> CameraConfig:
    return CameraConfig(
        device="/dev/video0",
        mode_id="test",
        width=640,
        height=480,
        ndim=3,
        channels=3,
        spec_fps=30.0,
        recommended_fps=29.5,
        input_format="mjpeg",
    )


def test_open_and_read_with_mock_capture():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, frame)

    mock_cv2 = MagicMock()
    mock_cv2.VideoCapture.return_value = mock_cap
    mock_cv2.CAP_V4L2 = 200
    mock_cv2.CAP_PROP_FOURCC = 6
    mock_cv2.CAP_PROP_FRAME_WIDTH = 3
    mock_cv2.CAP_PROP_FRAME_HEIGHT = 4
    mock_cv2.CAP_PROP_FPS = 5
    mock_cv2.VideoWriter_fourcc.return_value = 0

    camera = Camera(_camera_config())
    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        camera.open()
        assert camera.applied_fps == pytest.approx(29.5)
        assert camera.capture_fps == pytest.approx(29.5)
        result = camera.read()
        camera.close()

    assert np.array_equal(result, frame)
    assert camera.applied_fps is None
    mock_cap.release.assert_called_once()
    mock_cap.set.assert_any_call(mock_cv2.CAP_PROP_FPS, 29.5)


def test_read_without_open_raises():
    camera = Camera(_camera_config())
    with pytest.raises(CameraError, match="not open"):
        camera.read()


def test_read_rejects_wrong_shape():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))

    mock_cv2 = MagicMock()
    mock_cv2.VideoCapture.return_value = mock_cap
    mock_cv2.CAP_V4L2 = 200
    mock_cv2.CAP_PROP_FOURCC = 6
    mock_cv2.CAP_PROP_FRAME_WIDTH = 3
    mock_cv2.CAP_PROP_FRAME_HEIGHT = 4
    mock_cv2.CAP_PROP_FPS = 5
    mock_cv2.VideoWriter_fourcc.return_value = 0

    camera = Camera(_camera_config())
    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        camera.open()
        with pytest.raises(CameraError, match="480x640x3"):
            camera.read()


def test_applied_fps_unset_until_open():
    camera = Camera(_camera_config())
    assert camera.applied_fps is None
    assert camera.capture_fps == pytest.approx(29.5)


def test_last_measured_fps_unset_until_measure():
    camera = Camera(_camera_config())
    assert not camera.has_measured_fps
    with pytest.raises(CameraError, match="no measured fps yet"):
        _ = camera.last_measured_fps


def test_measure_fps_from_frame_times():
    camera = Camera(_camera_config())
    camera._frame_times.extend([0.0, 0.5, 1.0])

    measured = camera.measure_fps()

    assert measured == pytest.approx(3.0)
    assert camera.has_measured_fps
    assert camera.last_measured_fps == pytest.approx(3.0)


def test_measure_fps_raises_without_enough_frames():
    camera = Camera(_camera_config())
    with pytest.raises(CameraError, match="at least 2 frame timestamps"):
        camera.measure_fps()


def test_apply_measured_fps_sets_cap_prop():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    mock_cv2 = MagicMock()
    mock_cv2.CAP_PROP_FPS = 5

    camera = Camera(_camera_config())
    camera._cap = mock_cap
    camera._last_measured_fps = 27.3

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        applied = camera.apply_measured_fps(27.3)

    assert applied == pytest.approx(27.3)
    assert camera.applied_fps == pytest.approx(27.3)
    mock_cap.set.assert_called_once_with(mock_cv2.CAP_PROP_FPS, 27.3)


def test_measure_fps_apply_updates_capture():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    mock_cv2 = MagicMock()
    mock_cv2.CAP_PROP_FPS = 5

    camera = Camera(_camera_config())
    camera._cap = mock_cap
    camera._frame_times.extend([0.0, 0.5, 1.0])

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        measured = camera.measure_fps(apply=True)

    assert measured == pytest.approx(3.0)
    assert camera.applied_fps == pytest.approx(3.0)
    mock_cap.set.assert_called_once_with(mock_cv2.CAP_PROP_FPS, 3.0)


def test_apply_measured_fps_without_open_raises():
    camera = Camera(_camera_config())
    with pytest.raises(CameraError, match="not open"):
        camera.apply_measured_fps(29.5)


def test_apply_measured_fps_rejects_non_positive():
    camera = Camera(_camera_config())
    camera._cap = MagicMock()

    with pytest.raises(CameraError, match="greater than 0"):
        camera.apply_measured_fps(0.0)
