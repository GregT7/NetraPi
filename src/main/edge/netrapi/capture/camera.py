from __future__ import annotations

import time
from collections import deque
from typing import Deque

import numpy as np

from config.types import CameraConfig

from netrapi.exceptions import CameraError


def fourcc_for_input_format(input_format: str) -> int:
    import cv2

    normalized = input_format.strip().lower()
    if normalized in {"mjpeg", "mjpg"}:
        return cv2.VideoWriter_fourcc(*"MJPG")
    if normalized in {"yuyv", "yuy2", "yuyv422"}:
        return cv2.VideoWriter_fourcc(*"YUYV")
    return cv2.VideoWriter_fourcc(*"MJPG")


def _expected_capture_shape(*, height: int, width: int, channels: int) -> str:
    return f"{height}x{width}x{channels}"


def _validate_capture_frame(
    frame: np.ndarray,
    *,
    ndim: int,
    height: int,
    width: int,
    channels: int,
) -> bool:
    array = np.asarray(frame)

    wrong_rank = array.ndim != ndim
    wrong_channels = False
    wrong_height = False
    wrong_width = False

    if not wrong_rank:
        frame_height, frame_width, channel_count = array.shape
        wrong_channels = channel_count != channels
        wrong_height = frame_height != height
        wrong_width = frame_width != width

    if wrong_rank or wrong_channels or wrong_height or wrong_width:
        return False
    return True


class Camera:
    def __init__(self, config: CameraConfig) -> None:
        self._config = config
        self._cap = None
        self._frame_times: Deque[float] = deque(maxlen=120)
        self._last_measured_fps: float = 0.0
        self._applied_fps: float | None = None

    @property
    def config(self) -> CameraConfig:
        return self._config

    @property
    def has_measured_fps(self) -> bool:
        return self._last_measured_fps > 0.0

    @property
    def last_measured_fps(self) -> float:
        if not self.has_measured_fps:
            raise CameraError("no measured fps yet; call measure_fps() after reading frames")
        return self._last_measured_fps

    @property
    def applied_fps(self) -> float | None:
        return self._applied_fps

    @property
    def capture_fps(self) -> float:
        """FPS in use for capture and clip encoding (applied rate, or config before open)."""
        if self._applied_fps is not None:
            return self._applied_fps
        return float(self._config.recommended_fps)

    def open(self) -> None:
        import cv2

        self.close()
        cap = cv2.VideoCapture(self._config.device, cv2.CAP_V4L2)
        if not cap.isOpened():
            raise CameraError(f"Cannot open camera device {self._config.device}")

        cap.set(cv2.CAP_PROP_FOURCC, fourcc_for_input_format(self._config.input_format))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._config.width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._config.height))
        rate = float(self._config.recommended_fps)
        cap.set(cv2.CAP_PROP_FPS, rate)
        self._cap = cap
        self._applied_fps = rate

    def read(self) -> np.ndarray:
        if self._cap is None:
            raise CameraError("camera is not open")

        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise CameraError("failed to read frame from camera")

        array = np.asarray(frame)
        expected = _expected_capture_shape(
            height=self._config.height,
            width=self._config.width,
            channels=self._config.channels,
        )
        if not _validate_capture_frame(
            array,
            ndim=self._config.ndim,
            height=self._config.height,
            width=self._config.width,
            channels=self._config.channels,
        ):
            raise CameraError(
                f"camera frame shape must be {expected}, got {tuple(array.shape)}"
            )

        now = time.monotonic()
        self._frame_times.append(now)
        return array

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._applied_fps = None

    def measure_fps(self, *, apply: bool = False) -> float:
        if len(self._frame_times) < 2:
            raise CameraError(
                "cannot measure fps: need at least 2 frame timestamps from read()"
            )

        elapsed = self._frame_times[-1] - self._frame_times[0]
        if elapsed <= 0:
            raise CameraError("cannot measure fps: frame timestamps have zero span")

        fps = len(self._frame_times) / elapsed
        if fps <= 0:
            raise CameraError(f"cannot measure fps: computed rate {fps} is not positive")

        self._last_measured_fps = fps
        if apply:
            self.apply_measured_fps(fps)
        return fps

    def apply_measured_fps(self, fps: float) -> float:
        """Set CAP_PROP_FPS on the open capture to the given sustained rate."""
        if self._cap is None:
            raise CameraError("camera is not open")
        if fps <= 0:
            raise CameraError(f"fps must be greater than 0, got {fps}")

        import cv2

        rate = float(fps)
        self._cap.set(cv2.CAP_PROP_FPS, rate)
        self._applied_fps = rate
        return rate
