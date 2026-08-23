from __future__ import annotations

from dataclasses import dataclass

from netrapi.events.enums import StopSignEnum


@dataclass(frozen=True)
class ApproachSnapshot:
    peak_area_pct: float
    approach_duration_s: float
    increasing_fraction: float
    log_linear_r2: float
    drop_duration_s: float
    post_drop_holds: bool
    fail_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class DrivingEvent:
    type: StopSignEnum
    knn_stage1: tuple[float, ...] | None = None
    knn_stage2: tuple[float, ...] | None = None
    approach: ApproachSnapshot | None = None

    @property
    def is_unsafe(self) -> bool:
        return self.type.is_unsafe
