"""
Record from V4L2, write a temporary mp4v file, then run ffmpeg to:
  1) fix playback speed (setpts: catalog/header fps vs real fps = frames/elapsed)
  2) re-encode H.264 (better quality than OpenCV mp4v)

Requires: ffmpeg on PATH (e.g. sudo apt install ffmpeg).

catalog_fps = fps from camera.json = OpenCV VideoWriter fps = value players read as "header" fps.
If the Pi only delivers ~12 frames/s while the header says 30, playback looks ~2x fast until ffmpeg fixes it.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import cv2

_TP04_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TP04_DIR.parent.parent
CAMERA_MODES_FILE = _REPO_ROOT / "src" / "config" / "camera.json"
OUTPUT_PATH = str(_TP04_DIR / "demo_run.mp4")
# Match low-latency preview: ffplay -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 /dev/video0
SELECTED_MODE_ID = "mjpeg_1280x720_30"

TOTAL_TIME = 60
V4L2_DEVICE = "/dev/video0"
# Minimize V4L2 frame queue (OpenCV counterpart to ffplay -fflags nobuffer style capture).
V4L2_BUFFER_FRAMES = 1
ROTATION = 180
PREVIEW_WINDOW = "preview (q = quit)"
PREVIEW_MAX_WIDTH = 960
PREVIEW_MAX_HEIGHT = 540
PREVIEW_WINDOW_X = 40
PREVIEW_WINDOW_Y = 60
FFMPEG_CRF = 20
# Tone controls to reduce washed-out footage.
TONE_CONTRAST = 0.90
TONE_BRIGHTNESS = -20.0


def _load_mode(path: Path, mode_id: str) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    for m in data.get("modes") or []:
        if m.get("id") == mode_id:
            return m
    ids = ", ".join(sorted(str(x.get("id")) for x in data.get("modes") or [] if x.get("id")))
    raise ValueError(f"Unknown mode {mode_id!r}. Options: {ids}")


def _fourcc(cap: cv2.VideoCapture, fmt: str) -> None:
    f = fmt.lower()
    if f == "mjpeg":
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    elif f in ("yuyv422", "yuyv"):
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))


def _rotate(frame, degrees: int):
    d = degrees % 360
    if d == 0:
        return frame
    if d == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if d == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if d == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"ROTATION must be 0, 90, 180, or 270; got {degrees}")


def _preview_size(fw: int, fh: int, mx: int, my: int) -> Tuple[int, int]:
    if fw <= mx and fh <= my:
        return fw, fh
    s = min(mx / fw, my / fh)
    return max(1, int(round(fw * s))), max(1, int(round(fh * s)))


def _adjust_tone(frame, contrast: float, brightness: float):
    if contrast == 1.0 and brightness == 0.0:
        return frame
    return cv2.addWeighted(frame, contrast, frame, 0.0, brightness)


def main() -> int:
    mode = _load_mode(CAMERA_MODES_FILE, SELECTED_MODE_ID)
    w0, h0 = int(mode["width"]), int(mode["height"])
    catalog_fps = float(mode["fps"])

    cap = cv2.VideoCapture(V4L2_DEVICE, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"Cannot open {V4L2_DEVICE}")
        return 1
    _fourcc(cap, str(mode["input_format"]))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(w0))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(h0))
    cap.set(cv2.CAP_PROP_FPS, catalog_fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, V4L2_BUFFER_FRAMES)
    cap.read()

    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        print("No frame from camera")
        return 1
    toned0 = _adjust_tone(frame, TONE_CONTRAST, TONE_BRIGHTNESS)
    out0 = _rotate(toned0, ROTATION)
    oh, ow = out0.shape[:2]

    tmp_path = OUTPUT_PATH + ".tmp.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp_path, fourcc, catalog_fps, (ow, oh))
    if not writer.isOpened():
        cap.release()
        print(f"Cannot open VideoWriter for {tmp_path!r}")
        return 1

    pw, ph = _preview_size(ow, oh, PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT)
    cv2.namedWindow(PREVIEW_WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(PREVIEW_WINDOW, pw, ph)

    writer.write(out0)
    frames = 1
    # Use monotonic() for the capture window (real seconds). On some ARM/Pi setups perf_counter()
    # can drift from wall time and shorten a "60s" loop (~37s observed vs TOTAL_TIME).
    t0 = time.monotonic()
    deadline = t0 + TOTAL_TIME
    placed = False
    try:
        while time.monotonic() < deadline:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Stream ended")
                return 1
            toned = _adjust_tone(frame, TONE_CONTRAST, TONE_BRIGHTNESS)
            out = _rotate(toned, ROTATION)
            writer.write(out)
            frames += 1
            pv = cv2.resize(out, (pw, ph), interpolation=cv2.INTER_AREA)
            cv2.imshow(PREVIEW_WINDOW, pv)
            if not placed:
                cv2.moveWindow(PREVIEW_WINDOW, PREVIEW_WINDOW_X, PREVIEW_WINDOW_Y)
                placed = True
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
    finally:
        writer.release()
        cap.release()
        cv2.destroyAllWindows()

    elapsed = time.monotonic() - t0
    actual_fps = frames / elapsed if elapsed > 0 else 0.0
    ratio = catalog_fps / actual_fps if actual_fps > 1e-6 else 1.0

    print(
        f"{frames} frames / {elapsed:.1f}s wall -> {actual_fps:.2f} fps sustained | "
        f"header/catalog fps {catalog_fps:g} | setpts x {ratio:.4f}"
    )

    vf = f"setpts=PTS*{ratio:.8f}"
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        tmp_path,
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        str(FFMPEG_CRF),
        "-pix_fmt",
        "yuv420p",
        OUTPUT_PATH,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as e:
        print(f"ffmpeg not found ({e}). Raw clip kept: {tmp_path}")
        return 1
    if r.returncode != 0:
        print(f"ffmpeg failed (exit {r.returncode}). Raw clip kept: {tmp_path}")
        if r.stderr:
            print(r.stderr.strip())
        return 1

    if os.path.isfile(tmp_path):
        os.remove(tmp_path)
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as e:
        print(e)
        sys.exit(1)
    except cv2.error as e:
        print(e)
        sys.exit(1)
