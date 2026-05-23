from __future__ import annotations

from enum import Enum


class Stage1Label(Enum):
    """Labels emitted by the stage-1 kNN (safe vs unsafe bucket)."""

    COMPLETE_STOP = "complete-stop"
    ROLLING_OR_RUN_THROUGH = "rolling-or-run-through"


class Stage2Label(Enum):
    """Labels emitted by the stage-2 kNN (rolling vs run-through)."""

    ROLLING_STOP = "rolling-stop"
    RUN_THROUGH = "run-through"
