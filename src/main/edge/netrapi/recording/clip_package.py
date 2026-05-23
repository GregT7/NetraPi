from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass(frozen=True)
class ClipPackage:
    pre_frames: list[np.ndarray]
    post_frames: list[np.ndarray]
    triggered_at: datetime
    event_index: int

    @classmethod
    def build(
        cls,
        pre_frames: list[np.ndarray],
        post_frames: list[np.ndarray],
        *,
        triggered_at: datetime | None = None,
        event_index: int = 1,
    ) -> ClipPackage:
        return cls(
            [np.asarray(frame).copy() for frame in pre_frames],
            [np.asarray(frame).copy() for frame in post_frames],
            triggered_at or datetime.now(),
            event_index,
        )
