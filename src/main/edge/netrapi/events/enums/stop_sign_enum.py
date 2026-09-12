from __future__ import annotations

from enum import Enum


class StopSignEnum(Enum):
    ROLLING_STOP = ("stop_sign_rolling_stop", True, "rolling-stop")
    RUN_THROUGH = ("stop_sign_run_through", True, "run-through")
    COMPLETE_STOP = ("stop_sign_complete_stop", False, "complete-stop")

    def __new__(cls, value: str, is_unsafe: bool, model_label: str) -> StopSignEnum:
        member = object.__new__(cls)
        member._value_ = value
        member.is_unsafe = is_unsafe
        member.model_label = model_label
        return member

    @property
    def beep_count(self) -> int:
        """Audible pulses after classify: complete=1, rolling=2, run-through=3."""
        if self is StopSignEnum.RUN_THROUGH:
            return 3
        if self is StopSignEnum.ROLLING_STOP:
            return 2
        return 1

    @classmethod
    def from_model_label(cls, label: str) -> StopSignEnum:
        for member in cls:
            if member.model_label == label:
                return member
        raise ValueError(f"Unknown stop-sign model label: {label!r}")
