"""ROI Farneback optical-flow motion scoring for the live EventManager path."""

from __future__ import annotations

import cv2
import numpy as np

from config.types import MotionConfig


def _roi_slices(height: int, width: int, roi: dict[str, float]) -> tuple[slice, slice]:
    y0 = int(roi["y_min"] * height)
    y1 = int(roi["y_max"] * height)
    x0 = int(roi["x_min"] * width)
    x1 = int(roi["x_max"] * width)
    y0 = max(0, min(height - 1, y0))
    y1 = max(y0 + 1, min(height, y1))
    x0 = max(0, min(width - 1, x0))
    x1 = max(x0 + 1, min(width, x1))
    return slice(y0, y1), slice(x0, x1)


def prepare_gray(frame_bgr: np.ndarray, flow_scale: float) -> np.ndarray:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    if flow_scale == 1.0:
        return gray
    return cv2.resize(
        gray,
        (max(1, int(gray.shape[1] * flow_scale)), max(1, int(gray.shape[0] * flow_scale))),
        interpolation=cv2.INTER_AREA,
    )


def raw_flow_score(gray_prev: np.ndarray, gray_curr: np.ndarray, config: MotionConfig) -> float:
    fb = config.farneback
    flow = cv2.calcOpticalFlowFarneback(
        gray_prev,
        gray_curr,
        None,
        float(fb["pyr_scale"]),
        int(fb["levels"]),
        int(fb["winsize"]),
        int(fb["iterations"]),
        int(fb["poly_n"]),
        float(fb["poly_sigma"]),
        0,
    )
    magnitude, _angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    y_slice, x_slice = _roi_slices(magnitude.shape[0], magnitude.shape[1], config.motion_roi)
    roi_values = magnitude[y_slice, x_slice]
    if roi_values.size == 0:
        return 0.0
    return float(np.percentile(roi_values, 75))


class LiveMotionTracker:
    """Incremental ROI optical flow with trailing-window smoothing."""

    def __init__(self, motion_config: MotionConfig) -> None:
        self._config = motion_config
        self._prev_gray: np.ndarray | None = None
        self._raw_scores: list[float] = []

    def reset(self) -> None:
        self._prev_gray = None
        self._raw_scores.clear()

    def prime(self, frame_bgr: np.ndarray) -> None:
        """Cache grayscale so the first post-T0 score uses frame T0-1 -> T0 flow."""
        self._prev_gray = prepare_gray(frame_bgr, self._config.flow_scale)
        self._raw_scores.clear()

    def score(self, frame_bgr: np.ndarray) -> float:
        """Return smoothed motion score for the current frame vs previous gray."""
        gray = prepare_gray(frame_bgr, self._config.flow_scale)
        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_gray = gray
            self._raw_scores.append(0.0)
            return 0.0
        value = raw_flow_score(self._prev_gray, gray, self._config)
        self._prev_gray = gray
        self._raw_scores.append(value)
        return self.smoothed()

    def smoothed(self) -> float:
        window = max(1, self._config.motion_smoothing_window)
        if not self._raw_scores:
            return 0.0
        chunk = self._raw_scores[-window:]
        return sum(chunk) / len(chunk)
