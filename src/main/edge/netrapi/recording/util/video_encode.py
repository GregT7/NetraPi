from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from netrapi.exceptions import RecordingError


def _close_stdin(process: subprocess.Popen[bytes]) -> None:
    """Close ffmpeg stdin; ignore pipe already-closed races on close/flush.

    Clears ``process.stdin`` so a later ``communicate()`` does not close again
    (CPython only ignores BrokenPipeError there, not ``flush of closed file``).
    """
    stdin = process.stdin
    if stdin is None:
        return
    try:
        stdin.close()
    except (BrokenPipeError, ValueError):
        # ffmpeg may exit early; close then raises "flush of closed file".
        pass
    process.stdin = None


def write_h264_mp4(
    *,
    frames: list[np.ndarray],
    fps: float,
    output_path: Path,
    crf: int,
) -> None:
    if len(frames) < 2:
        raise RecordingError(f"need at least 2 frames to encode MP4, got {len(frames)}")
    if fps <= 0:
        raise RecordingError(f"fps must be greater than 0, got {fps}")
    if crf < 0:
        raise RecordingError(f"crf must be >= 0, got {crf}")

    first = np.asarray(frames[0])
    if first.ndim != 3 or first.shape[2] != 3:
        raise RecordingError(f"frames must be HxWx3 BGR arrays, got shape {first.shape}")

    height, width = first.shape[:2]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.8f}",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RecordingError("ffmpeg not found on PATH; install ffmpeg for MP4 output") from exc

    assert process.stdin is not None
    stderr = b""
    try:
        for index, frame in enumerate(frames):
            array = np.asarray(frame)
            if array.shape[:2] != (height, width) or array.shape[2] != 3:
                raise RecordingError(
                    f"frame {index} shape {array.shape} does not match first frame {(height, width, 3)}"
                )
            if not array.flags.c_contiguous:
                array = np.ascontiguousarray(array)
            if array.dtype != np.uint8:
                array = array.astype(np.uint8, copy=False)
            process.stdin.write(array.tobytes())
    except RecordingError:
        _close_stdin(process)
        process.kill()
        process.wait()
        raise
    except Exception as exc:
        _close_stdin(process)
        process.kill()
        process.wait()
        raise RecordingError(f"failed while piping frames to ffmpeg: {exc}") from exc
    else:
        _close_stdin(process)
        _, stderr = process.communicate()

    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip() or f"ffmpeg exit {process.returncode}"
        raise RecordingError(f"ffmpeg failed to encode {output_path.name}: {detail}")

    # H.264 of uniform frames is often much smaller than one uncompressed frame;
    # only reject a missing or empty mux.
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RecordingError(f"ffmpeg produced no output at {output_path}")
