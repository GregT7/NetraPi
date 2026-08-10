from __future__ import annotations

import numpy as np

from config.types import PreviewConfig


class PreviewUI:
    def __init__(self, config: PreviewConfig) -> None:
        self._config = config
        self._enabled = config.enabled
        self._window_open = False

    @property
    def config(self) -> PreviewConfig:
        return self._config

    @property
    def enabled(self) -> bool:
        return self._enabled

    def open_window(self) -> None:
        import cv2

        cv2.namedWindow(self._config.window_name, cv2.WINDOW_NORMAL)
        cv2.moveWindow(self._config.window_name, self._config.window_x, self._config.window_y)
        self._window_open = True

    def show(self, frame: np.ndarray) -> int:
        if not self._enabled:
            return 255
        if not self._window_open:
            self.open_window()

        import cv2

        display = self._fit_frame(np.asarray(frame))
        cv2.imshow(self._config.window_name, display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(self._config.toggle_key):
            self.toggle()
        return key

    def toggle(self) -> bool:
        self._enabled = not self._enabled
        if not self._enabled:
            self._close_window()
        return self._enabled

    def _close_window(self) -> None:
        if not self._window_open:
            return

        import cv2

        cv2.destroyWindow(self._config.window_name)
        self._window_open = False

    def _fit_frame(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        max_width = self._config.max_width
        max_height = self._config.max_height
        if width <= max_width and height <= max_height:
            return frame

        import cv2

        scale = min(max_width / width, max_height / height)
        new_width = max(1, int(round(width * scale)))
        new_height = max(1, int(round(height * scale)))
        return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
