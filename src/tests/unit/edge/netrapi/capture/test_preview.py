from unittest.mock import MagicMock, patch

import numpy as np

from config.types import PreviewConfig
from netrapi.capture import PreviewUI


def _preview_config(*, enabled: bool = True) -> PreviewConfig:
    return PreviewConfig(
        window_name="netrapi-preview",
        window_x=10,
        window_y=20,
        max_width=320,
        max_height=240,
        enabled=enabled,
        toggle_key="t",
    )


def test_open_window_calls_cv2_named_window_and_move():
    config = _preview_config()
    mock_cv2 = MagicMock()
    mock_cv2.WINDOW_NORMAL = 1

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        preview = PreviewUI(config)
        preview.open_window()

    mock_cv2.namedWindow.assert_called_once_with(config.window_name, mock_cv2.WINDOW_NORMAL)
    mock_cv2.moveWindow.assert_called_once_with(config.window_name, config.window_x, config.window_y)


def test_show_opens_window_and_displays_frame():
    config = _preview_config()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_cv2 = MagicMock()
    mock_cv2.WINDOW_NORMAL = 1

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        preview = PreviewUI(config)
        preview.show(frame)

    mock_cv2.namedWindow.assert_called_once_with(config.window_name, mock_cv2.WINDOW_NORMAL)
    mock_cv2.moveWindow.assert_called_once_with(config.window_name, config.window_x, config.window_y)
    mock_cv2.imshow.assert_called_once()
    window_name, displayed = mock_cv2.imshow.call_args[0]
    assert window_name == config.window_name
    assert displayed is frame
    mock_cv2.waitKey.assert_called_once_with(1)


def test_show_when_disabled_does_not_touch_cv2():
    mock_cv2 = MagicMock()

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        preview = PreviewUI(_preview_config(enabled=False))
        preview.show(np.zeros((100, 100, 3), dtype=np.uint8))

    mock_cv2.namedWindow.assert_not_called()
    mock_cv2.imshow.assert_not_called()


def test_preview_starts_disabled_when_config_enabled_false():
    preview = PreviewUI(_preview_config(enabled=False))

    assert preview.enabled is False


def test_preview_toggle_closes_window():
    config = _preview_config()
    mock_cv2 = MagicMock()
    mock_cv2.WINDOW_NORMAL = 1

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        preview = PreviewUI(config)
        preview.open_window()
        assert preview.toggle() is False

    mock_cv2.destroyWindow.assert_called_once_with(config.window_name)
    assert preview.enabled is False


def test_preview_toggle():
    preview = PreviewUI(_preview_config())

    assert preview.toggle() is False
    assert preview.toggle() is True


def test_show_press_t_toggles_off_and_closes_window():
    config = _preview_config()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_cv2 = MagicMock()
    mock_cv2.WINDOW_NORMAL = 1
    mock_cv2.waitKey.return_value = ord(config.toggle_key)

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        preview = PreviewUI(config)
        preview.show(frame)

    assert preview.enabled is False
    mock_cv2.destroyWindow.assert_called_once_with(config.window_name)


def test_show_other_key_does_not_toggle():
    config = _preview_config()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    mock_cv2 = MagicMock()
    mock_cv2.WINDOW_NORMAL = 1
    mock_cv2.waitKey.return_value = ord("q")

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        preview = PreviewUI(config)
        preview.show(frame)

    assert preview.enabled is True
    mock_cv2.destroyWindow.assert_not_called()
