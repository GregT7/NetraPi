"""
AT-3.4 clip replay: same per-frame approach + motion window + kNN as the live bench.

Runs on existing MP4 clips (laptop CPU TFLite) and overlays approach / classification
banners matching the live HDMI bench.

Usage (from repo root, batch_analysis venv):

    python src/tests/integration/at_3_4/prepare_at_3_4_config.py
    python src/tests/integration/at_3_4/at_3_4_replay_clip_classification.py \\
        --clip-id 10 --show-window
    python src/tests/integration/at_3_4/at_3_4_replay_clip_classification.py \\
        --clip-path vids/unsafe_events/clips/clip_010_....mp4 --output replay.mp4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
BATCH_LIB = REPO_ROOT / "src/tests/analysis/batch_analysis/scripts/lib"
CONFIG_DIR = SCRIPT_DIR / "config"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from at_3_4_pipeline import (
    ApproachCycle,
    arm_approach_cycle,
    classify_approach_cycle,
    lock_cycle_buffers,
    safety_label,
)

PREVIEW_WINDOW = "AT-3.4 Clip Classification Replay"
PREVIEW_MAX_WIDTH = 1280
PREVIEW_MAX_HEIGHT = 720
BANNER_DWELL_S = 10.0


class LiveMotionTracker:
    """Incremental ROI optical flow; prime_gray() while idle, score() in post-T0 window."""

    def __init__(self, motion_config) -> None:
        self._config = motion_config
        self._prev_gray: np.ndarray | None = None

    def reset(self) -> None:
        self._prev_gray = None

    def prime_gray(self, frame_bgr: np.ndarray) -> None:
        """Cheap grayscale cache so the first post-T0 score uses frame T0-1 -> T0 flow."""
        from motion_score_series import _prepare_gray

        self._prev_gray = _prepare_gray(frame_bgr, self._config.flow_scale)

    def score(self, frame_bgr: np.ndarray) -> float:
        from motion_score_series import _prepare_gray, _raw_flow_score

        gray = _prepare_gray(frame_bgr, self._config.flow_scale)
        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_gray = gray
            return 0.0
        value = _raw_flow_score(self._prev_gray, gray, self._config)
        self._prev_gray = gray
        return value

    def smoothed(self, raw_scores: list[float]) -> float:
        window = max(1, self._config.motion_smoothing_window)
        if not raw_scores:
            return 0.0
        chunk = raw_scores[-window:]
        return sum(chunk) / len(chunk)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AT-3.4: replay approach + motion + kNN classification on a stored clip."
    )
    clip_group = parser.add_mutually_exclusive_group(required=True)
    clip_group.add_argument("--clip-id", type=int, help="Clip id (e.g. 10 for clip_010_...)")
    clip_group.add_argument("--clip-path", type=Path, help="Path to an MP4 clip")
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument("--show-window", action="store_true", help="Open OpenCV preview")
    parser.add_argument("--output", type=Path, help="Optional MP4 output path")
    parser.add_argument("--write-events", type=Path, help="Optional JSONL event log path")
    parser.add_argument("--max-seconds", type=float, help="Stop replay after this many seconds")
    parser.add_argument(
        "--allow-repeat-cycles",
        action="store_true",
        help="After banners clear, allow another approach cycle (default: one cycle per clip)",
    )
    return parser.parse_args()


def _bootstrap_analysis_lib() -> None:
    lib_str = str(BATCH_LIB)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_configs(config_dir: Path):
    from motion_score_series import motion_config_from_dict
    from stop_sign_approach_pattern import ApproachDropConfig

    approach_raw = _load_json(config_dir / "approach_config.json")
    fields = {name for name in ApproachDropConfig.__dataclass_fields__}
    approach_config = ApproachDropConfig(
        **{key: value for key, value in approach_raw.items() if key in fields}
    )
    motion_config = motion_config_from_dict(_load_json(config_dir / "motion_config.json"))
    metrics_config = _load_json(config_dir / "metrics_config.json")
    post_drop_window_s = float(metrics_config["post_drop_window_s"])
    return approach_config, motion_config, post_drop_window_s


def _load_knn_pipelines(config_dir: Path):
    try:
        import joblib
    except ImportError as exc:
        raise SystemExit("joblib is required: pip install joblib scikit-learn") from exc

    stage1_path = config_dir / "knn_stage1.joblib"
    stage2_path = config_dir / "knn_stage2.joblib"
    if not stage1_path.is_file():
        raise FileNotFoundError(
            f"Missing {stage1_path.name}. Run prepare_at_3_4_config.py first."
        )
    stage1 = joblib.load(stage1_path)
    stage2 = joblib.load(stage2_path) if stage2_path.is_file() else None
    return stage1, stage2


def _classification_banner_bgr(stage1_predicted: str) -> tuple[int, int, int]:
    if stage1_predicted == "complete-stop":
        return (255, 128, 0)
    return (0, 0, 220)


def _preview_size(frame_width: int, frame_height: int) -> tuple[int, int]:
    if frame_width <= PREVIEW_MAX_WIDTH and frame_height <= PREVIEW_MAX_HEIGHT:
        return frame_width, frame_height
    scale = min(PREVIEW_MAX_WIDTH / frame_width, PREVIEW_MAX_HEIGHT / frame_height)
    return (
        max(1, int(round(frame_width * scale))),
        max(1, int(round(frame_height * scale))),
    )


def _frame_for_preview(frame_bgr: np.ndarray, preview_size: tuple[int, int]) -> np.ndarray:
    preview_w, preview_h = preview_size
    height, width = frame_bgr.shape[:2]
    if (width, height) == (preview_w, preview_h):
        return frame_bgr
    return cv2.resize(frame_bgr, (preview_w, preview_h), interpolation=cv2.INTER_AREA)


def _draw_banner(
    frame_bgr: np.ndarray,
    *,
    top_y: int,
    height: int,
    text: str,
    fill_bgr: tuple[int, int, int],
    text_scale: float = 0.85,
) -> int:
    width = frame_bgr.shape[1]
    cv2.rectangle(frame_bgr, (0, top_y), (width, top_y + height), fill_bgr, -1)
    cv2.putText(
        frame_bgr,
        text,
        (12, top_y + int(height * 0.68)),
        cv2.FONT_HERSHEY_SIMPLEX,
        text_scale,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return top_y + height + 4


def _draw_detection(frame_bgr: np.ndarray, detection) -> None:
    from stop_sign_area_series import normalized_box_area

    height, width = frame_bgr.shape[:2]
    ymin, xmin, ymax, xmax = detection.box
    x1 = int(xmin * width)
    y1 = int(ymin * height)
    x2 = int(xmax * width)
    y2 = int(ymax * height)
    cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 255, 0), 4)
    area_pct = normalized_box_area(detection.box) * 100.0
    label = f"{detection.label} {detection.score:.2f} area={area_pct:.1f}%"
    cv2.putText(
        frame_bgr,
        label,
        (x1, max(24, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )


def _draw_overlay(
    frame_bgr: np.ndarray,
    *,
    clip_label: str,
    actual_class: str,
    elapsed_s: float,
    area_series_len: int,
    max_area_pct: float,
    cycle: ApproachCycle | None,
    banners_visible: bool,
) -> None:
    hud_lines = [
        f"AT-3.4 replay — {clip_label}",
        f"actual={actual_class} t={elapsed_s:.2f}s area_len={area_series_len} max_area={max_area_pct:.2f}%",
    ]
    y = 32
    for line in hud_lines:
        cv2.putText(
            frame_bgr,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame_bgr,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
        y += 30

    if not banners_visible or cycle is None:
        return

    banner_top = y + 8
    _draw_banner(
        frame_bgr,
        top_y=banner_top,
        height=56,
        text=f"APPROACH DETECTED @ t={cycle.t0_s:.3f}s",
        fill_bgr=(0, 180, 0),
        text_scale=0.85,
    )
    if cycle.classified and cycle.classify_at_s is not None and cycle.stage1_predicted:
        safety = safety_label(cycle.stage1_predicted)
        safety_suffix = f" ({safety})" if safety else ""
        banner_top = _draw_banner(
            frame_bgr,
            top_y=banner_top + 56,
            height=56,
            text=(
                f"CLASSIFICATION @ t={cycle.classify_at_s:.3f}s: "
                f"{cycle.stage1_predicted}{safety_suffix}"
            ),
            fill_bgr=_classification_banner_bgr(cycle.stage1_predicted),
            text_scale=0.78,
        )
        if cycle.e2e_predicted:
            _draw_banner(
                frame_bgr,
                top_y=banner_top,
                height=40,
                text=f"e2e: {cycle.e2e_predicted}",
                fill_bgr=_classification_banner_bgr(cycle.stage1_predicted),
                text_scale=0.68,
            )


def _resolve_clip_path(args: argparse.Namespace) -> Path:
    if args.clip_path is not None:
        path = args.clip_path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Clip not found: {path}")
        return path

    from clip_labels import clip_path_for_id
    from paths import clips_dir_path

    clip_path = clip_path_for_id(args.clip_id, clips_dir_path())
    if clip_path is None or not clip_path.is_file():
        raise FileNotFoundError(
            f"Clip not found for clip_id={args.clip_id} under {clips_dir_path()}"
        )
    return clip_path


def _actual_class_label(clip_path: Path) -> str:
    try:
        from clip_labels import category_for_clip

        return category_for_clip(clip_path.name)
    except Exception:
        return "?"


def _pick_best_detection(classifier, frame_bgr: np.ndarray):
    from stop_sign_area_series import filter_detections_by_center_x, max_stop_sign_area

    detections = classifier.classify(frame_bgr)
    filtered = filter_detections_by_center_x(detections, classifier.min_box_center_x)
    if not filtered:
        return None, 0.0
    best = max(filtered, key=lambda item: item.score)
    return best, max_stop_sign_area(filtered)


def _read_fps(capture: cv2.VideoCapture) -> float:
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    return fps if fps > 0 else 30.0


def _append_event(events: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    events.append(payload)


def replay_clip(
    *,
    clip_path: Path,
    actual_class: str,
    approach_config,
    motion_config,
    post_drop_window_s: float,
    stage1_pipeline,
    stage2_pipeline,
    classifier,
    show_window: bool,
    writer: cv2.VideoWriter | None,
    preview_size: tuple[int, int] | None,
    max_seconds: float | None,
    allow_repeat_cycles: bool,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    from per_frame_approach_sim import PerFrameConfig, detect_approach_per_frame

    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {clip_path}")

    fps = _read_fps(capture)
    per_frame_config = PerFrameConfig(post_drop_window_s=post_drop_window_s)
    motion_tracker = LiveMotionTracker(motion_config)

    area_series: list[float] = []
    max_area_pct = 0.0
    active_cycle: ApproachCycle | None = None
    banners_visible = False
    frame_index = 0
    approach_count = 0
    classification_count = 0
    cycle_locked = False

    _append_event(
        events,
        {"event": "replay_start", "clip": clip_path.name, "fps": round(fps, 3)},
    )

    while True:
        ok, frame_bgr = capture.read()
        if not ok or frame_bgr is None:
            break

        elapsed = frame_index / fps
        if max_seconds is not None and elapsed >= max_seconds:
            break

        display = frame_bgr.copy()
        track_approach = active_cycle is None and not cycle_locked

        if track_approach:
            detection, area_fraction = _pick_best_detection(classifier, frame_bgr)
            if detection is not None:
                _draw_detection(display, detection)

            area_series.append(area_fraction)
            max_area_pct = max(max_area_pct, area_fraction * 100.0)

            _detect_frame, detect_time_s = detect_approach_per_frame(
                area_series,
                fps,
                approach_config=approach_config,
                per_frame_config=per_frame_config,
            )
            _ = _detect_frame

            if detect_time_s is not None:
                active_cycle = arm_approach_cycle(
                    elapsed_s=elapsed,
                    area_series=area_series,
                    area_fraction=area_fraction,
                )
                banners_visible = True
                approach_count += 1
                _append_event(
                    events,
                    {
                        "event": "approach_detected",
                        "t0_s": round(elapsed, 3),
                        "detect_frame": active_cycle.detect_frame,
                        "area_at_detect": round(area_fraction, 5),
                    },
                )
                print(f"APPROACH @ t={elapsed:.3f}s", flush=True)

        in_motion_window = False
        if active_cycle is not None:
            window_end = active_cycle.t0_s + post_drop_window_s
            in_motion_window = active_cycle.t0_s <= elapsed <= window_end
            if in_motion_window:
                raw = motion_tracker.score(frame_bgr)
                active_cycle.motion_raw.append(raw)
                smoothed = motion_tracker.smoothed(active_cycle.motion_raw)
                active_cycle.motion_samples.append((elapsed, smoothed))

            if (
                not active_cycle.classified
                and elapsed >= window_end
                and active_cycle.motion_samples
            ):
                prediction = classify_approach_cycle(
                    active_cycle,
                    approach_config=approach_config,
                    motion_config=motion_config,
                    post_drop_window_s=post_drop_window_s,
                    stage1_pipeline=stage1_pipeline,
                    stage2_pipeline=stage2_pipeline,
                    fps=fps,
                )
                if prediction is not None:
                    active_cycle.classified = True
                    active_cycle.classify_at_s = elapsed
                    active_cycle.stage1_predicted = prediction["stage1_predicted"]
                    active_cycle.stage2_predicted = prediction["stage2_predicted"]
                    active_cycle.e2e_predicted = prediction["e2e_predicted"]
                    active_cycle.stage1_features = list(prediction["stage1_features"])
                    active_cycle.stage2_features = list(prediction["stage2_features"])
                    active_cycle.banners_clear_at_s = elapsed + BANNER_DWELL_S
                    classification_count += 1
                    if not allow_repeat_cycles:
                        cycle_locked = True
                        lock_cycle_buffers(
                            area_series=area_series,
                            motion_tracker=motion_tracker,
                        )
                    _append_event(
                        events,
                        {
                            "event": "classification",
                            "t0_s": round(active_cycle.t0_s, 3),
                            "classify_at_s": round(elapsed, 3),
                            "stage1_features": [
                                round(value, 5) for value in active_cycle.stage1_features
                            ],
                            "stage2_features": [
                                round(value, 5) for value in active_cycle.stage2_features
                            ],
                            "stage1": active_cycle.stage1_predicted,
                            "stage2": active_cycle.stage2_predicted,
                            "e2e": active_cycle.e2e_predicted,
                        },
                    )
                    print(
                        f"CLASSIFICATION @ t={elapsed:.3f}s: "
                        f"{active_cycle.stage1_predicted} / e2e={active_cycle.e2e_predicted}",
                        flush=True,
                    )

            if (
                active_cycle.banners_clear_at_s is not None
                and elapsed >= active_cycle.banners_clear_at_s
            ):
                _append_event(
                    events,
                    {"event": "banners_cleared", "at_s": round(elapsed, 3)},
                )
                active_cycle = None
                banners_visible = False

        if active_cycle is None and not cycle_locked:
            motion_tracker.prime_gray(frame_bgr)

        _draw_overlay(
            display,
            clip_label=clip_path.name,
            actual_class=actual_class,
            elapsed_s=elapsed,
            area_series_len=len(area_series),
            max_area_pct=max_area_pct,
            cycle=active_cycle if banners_visible else None,
            banners_visible=banners_visible,
        )

        if writer is not None:
            writer.write(display)
        if show_window and preview_size is not None:
            cv2.imshow(PREVIEW_WINDOW, _frame_for_preview(display, preview_size))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                print("Quit early.", flush=True)
                break

        frame_index += 1
        _ = in_motion_window

    capture.release()
    duration_s = frame_index / fps if fps > 0 else 0.0
    summary = {
        "clip": clip_path.name,
        "duration_s": round(duration_s, 3),
        "frames": frame_index,
        "approach_count": approach_count,
        "classification_count": classification_count,
        "max_area_pct": round(max_area_pct, 3),
    }
    _append_event(events, {"event": "replay_end", **summary})
    return summary


def main() -> int:
    args = parse_args()
    config_dir = args.config_dir.resolve()
    _bootstrap_analysis_lib()

    approach_config, motion_config, post_drop_window_s = _load_configs(config_dir)
    stage1_pipeline, stage2_pipeline = _load_knn_pipelines(config_dir)

    from stop_sign_area_series import try_build_classifier

    classifier, classifier_error = try_build_classifier()
    if classifier is None:
        print(classifier_error or "CPU classifier could not be loaded.", file=sys.stderr)
        return 1

    try:
        clip_path = _resolve_clip_path(args)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    actual_class = _actual_class_label(clip_path)
    print(f"Replaying: {clip_path.name} (actual={actual_class})", flush=True)
    print(f"Config: {config_dir}", flush=True)
    print(f"post_drop_window_s={post_drop_window_s}", flush=True)

    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        print(f"Could not open video: {clip_path}", file=sys.stderr)
        return 1
    fps = _read_fps(capture)
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()

    show_window = args.show_window or args.output is None
    preview_size: tuple[int, int] | None = None
    if show_window:
        preview_size = _preview_size(frame_width, frame_height)
        cv2.namedWindow(PREVIEW_WINDOW, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(PREVIEW_WINDOW, preview_size[0], preview_size[1])

    writer: cv2.VideoWriter | None = None
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            str(args.output),
            fourcc,
            fps,
            (frame_width, frame_height),
        )
        if not writer.isOpened():
            print(f"Could not open video writer: {args.output}", file=sys.stderr)
            return 1

    events: list[dict[str, Any]] = []
    try:
        summary = replay_clip(
            clip_path=clip_path,
            actual_class=actual_class,
            approach_config=approach_config,
            motion_config=motion_config,
            post_drop_window_s=post_drop_window_s,
            stage1_pipeline=stage1_pipeline,
            stage2_pipeline=stage2_pipeline,
            classifier=classifier,
            show_window=show_window,
            writer=writer,
            preview_size=preview_size,
            max_seconds=args.max_seconds,
            allow_repeat_cycles=args.allow_repeat_cycles,
            events=events,
        )
    finally:
        if writer is not None:
            writer.release()
        if show_window:
            cv2.destroyAllWindows()

    summary["actual_class"] = actual_class
    print("\n=== Replay summary ===", flush=True)
    for key, value in summary.items():
        print(f"  {key}: {value}", flush=True)

    if args.write_events is not None:
        args.write_events.parent.mkdir(parents=True, exist_ok=True)
        with args.write_events.open("w", encoding="utf-8") as handle:
            for item in events:
                handle.write(json.dumps(item) + "\n")
        print(f"Events written: {args.write_events.resolve()}", flush=True)

    if args.output is not None:
        print(f"Wrote: {args.output.resolve()}", flush=True)
    elif not args.show_window:
        print("No --output and no --show-window; nothing displayed.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
