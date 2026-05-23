from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Classification:
    label: str
    score: float
    box: tuple[float, float, float, float]
