from __future__ import annotations

from netrapi.exceptions import RecordingError


def encoding_fps(*, frame_count: int, first_at: float, last_at: float) -> float:
    if frame_count < 2:
        raise RecordingError(f"need at least 2 frames to compute encoding fps, got {frame_count}")
    elapsed = last_at - first_at
    if elapsed <= 0:
        raise RecordingError(f"capture span must be positive, got {elapsed}")
    fps = frame_count / elapsed
    if fps <= 0:
        raise RecordingError(f"computed encoding fps must be positive, got {fps}")
    return fps


def clip_encoding_fps(
    pre_span: tuple[int, float, float] | None,
    post_span: tuple[int, float, float] | None,
) -> float:
    spans = [span for span in (pre_span, post_span) if span is not None]
    if not spans:
        raise RecordingError("clip buffers have no capture timestamps")
    frame_count = sum(span[0] for span in spans)
    first_at = min(span[1] for span in spans)
    last_at = max(span[2] for span in spans)
    return encoding_fps(frame_count=frame_count, first_at=first_at, last_at=last_at)
