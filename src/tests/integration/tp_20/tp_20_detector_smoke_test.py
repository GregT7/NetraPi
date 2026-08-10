"""
TP-20: Detector on-device smoke (integration).

Runs the production ``Detector`` path on the Pi with Coral attached:
``load()`` → ``verify_tpu()`` → one ``classify(raw)`` on a camera frame.

Usage (from repo root, Pi venv with edge + tflite_runtime + OpenCV):

    python src/tests/integration/tp_20/tp_20_detector_smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
EDGE_DIR = SCRIPT_DIR.parents[3] / "main" / "edge"

WARMUP_FRAMES = 5


def _configure_import_path() -> None:
    edge_str = str(EDGE_DIR)
    if edge_str not in sys.path:
        sys.path.insert(0, edge_str)


def _read_camera_frame(app_config, *, warmup_frames: int) -> np.ndarray:
    from netrapi.capture import Camera
    from netrapi.exceptions import CameraError

    camera = Camera(app_config.camera)
    try:
        camera.open()
        for _ in range(max(warmup_frames, 0)):
            camera.read()
        return camera.read()
    except CameraError as exc:
        raise SystemExit(f"Camera error: {exc}") from exc
    finally:
        camera.close()


def _print_classifications(classifications) -> None:
    if not classifications:
        print("classify(raw): 0 detections (allowed classes may be absent in scene)")
        return

    print(f"classify(raw): {len(classifications)} detection(s)")
    for index, item in enumerate(classifications, start=1):
        ymin, xmin, ymax, xmax = item.box
        print(
            f"  [{index}] label={item.label!r} score={item.score:.3f} "
            f"box=(ymin={ymin:.3f}, xmin={xmin:.3f}, ymax={ymax:.3f}, xmax={xmax:.3f})"
        )


def main() -> int:
    _configure_import_path()
    from config.loader import AppConfig, ConfigError
    from main import DEFAULT_CONFIG_DIR, REPO_ROOT, _resolve_runtime_paths
    from netrapi.build import build_detector
    from netrapi.exceptions import DetectionError, NetraPiError

    config_dir = DEFAULT_CONFIG_DIR.resolve()

    try:
        app_config = AppConfig.load(config_dir)
        app_config = _resolve_runtime_paths(app_config, REPO_ROOT)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    print("TP-20: Detector on-device smoke")
    print(f"  config_dir: {config_dir}")
    print(f"  model_path: {app_config.detector.model_path}")
    print(f"  labels_path: {app_config.detector.labels_path}")
    print(f"  allowed_classes: {sorted(app_config.detector.allowed_classes)}")
    print(f"  warmup_frames: {WARMUP_FRAMES}")

    if not app_config.detector.model_path.is_file():
        print(f"Model file not found: {app_config.detector.model_path}", file=sys.stderr)
        return 1
    if not app_config.detector.labels_path.is_file():
        print(f"Labels file not found: {app_config.detector.labels_path}", file=sys.stderr)
        return 1

    try:
        print("\n[1/3] load() + verify_tpu() ...")
        detector = build_detector(app_config, verify_tpu=True)
        print("  verify_tpu(): OK")

        print(f"\n[2/3] capture frame (warmup={WARMUP_FRAMES}) ...")
        raw = _read_camera_frame(app_config, warmup_frames=WARMUP_FRAMES)
        print(f"  raw shape: {tuple(raw.shape)} dtype={raw.dtype}")

        print("\n[3/3] classify(raw) ...")
        classifications = detector.classify(raw)
        _print_classifications(classifications)
    except DetectionError as exc:
        print(f"Detector error: {exc}", file=sys.stderr)
        return 1
    except NetraPiError as exc:
        print(f"NetraPi error: {exc}", file=sys.stderr)
        return 1

    print("\nTP-20: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
