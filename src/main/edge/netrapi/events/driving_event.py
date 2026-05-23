from __future__ import annotations

from dataclasses import dataclass

from netrapi.events.enums import StopSignEnum


@dataclass(frozen=True)
class DrivingEvent:
    type: StopSignEnum

    @property
    def is_unsafe(self) -> bool:
        return self.type.is_unsafe
