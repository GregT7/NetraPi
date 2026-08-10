"""EventManager FSM phases."""

from __future__ import annotations

from enum import Enum, auto


class EventPhase(Enum):
    WATCHING = auto()
    COLLECT_POST_DROP = auto()
