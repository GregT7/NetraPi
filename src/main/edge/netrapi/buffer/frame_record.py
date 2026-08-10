from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from netrapi.buffer.classification import Classification


@dataclass
class FrameRecord:
    """One captured lap: raw sensor frame, processed display copy, optional detections."""

    raw: np.ndarray
    display: np.ndarray | None = None
    classifications: list[Classification] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.raw = np.asarray(self.raw)
        if self.display is None:
            self.display = self.raw.copy()
        else:
            self.display = np.asarray(self.display)

    def patch_classifications(self, classifications: list[Classification]) -> None:
        self.classifications = list(classifications)
