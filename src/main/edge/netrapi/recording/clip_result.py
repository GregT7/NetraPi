from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClipResult:
    clip_path: Path
    pre_frame_count: int
    post_frame_count: int
    pre_ok: bool
    post_ok: bool
    notes: str
