"""
AT-3.4: Live approach + motion + classification bench (Pi FPS + overlay).

Four keypress-advanced phases (~30s): baseline HUD, then complete-stop / rolling /
run-through with per-frame approach, 5s motion window, and sklearn kNN banners.

Usage (from repo root, Pi with camera + Coral):

    python src/tests/integration/at_3_4/prepare_at_3_4_config.py
    python src/tests/integration/at_3_4/at_3_4_live_motion_classification_benchmark.py \\
        --show-window --write-status
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    import tflite_runtime.interpreter as tflite
except ImportError as exc:
    raise SystemExit(
        "tflite_runtime is required (run on the Pi with Edge TPU delegate installed)."
    ) from exc

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
    max_stop_sign_area_fraction,
    safety_label,
)

MODEL_CANDIDATES = (
    REPO_ROOT / "src/main/edge/models/ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite",
    REPO_ROOT / "src/models/ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite",
)
LABEL_CANDIDATES = (
    REPO_ROOT / "src/main/edge/models/coco_labels.txt",
    REPO_ROOT / "src/models/coco_labels.txt",
)

CAMERA_INDEX = 0
DEFAULT_PHASE_SECONDS = 30
BANNER_DWELL_S = 10.0
PREVIEW_WINDOW = "AT-3.4 Live Motion Classification Bench"
PREVIEW_MAX_WIDTH = 1280
PREVIEW_MAX_HEIGHT = 720
PASS_FPS_DELTA_PCT = 40.0
PASS_APPROACH_MS_P95 = 33.0
LOG_PREFIX = "at_3_4"

PHASES = (
    {
        "phase": 1,
        "header": "Phase 1/4 — Baseline drive",
        "motion_enabled": False,
        "classify_enabled": False,
    },
    {
        "phase": 2,
        "header": "Phase 2/4 — Complete stop",
        "motion_enabled": True,
        "classify_enabled": True,
    },
    {
        "phase": 3,
        "header": "Phase 3/4 — Rolling stop",
        "motion_enabled": True,
        "classify_enabled": True,
    },
    {
        "phase": 4,
        "header": "Phase 4/4 — Run-through",
        "motion_enabled": True,
        "classify_enabled": True,
    },
)


@dataclass
class PhaseResult:
    phase: int
    title: str
    duration_s: float = 0.0
    lap_count: int = 0
    loop_fps: float = 0.0
    infer_ms_avg: float = 0.0
    approach_ms_avg: float = 0.0
    approach_ms_p95: float = 0.0
    approach_detected: bool = False
    classification_fired: bool = False
    approach_count: int = 0
    classification_count: int = 0
    motion_window_fps_min: float | None = None
    motion_window_fps_avg: float | None = None
    last_stage1: str = ""
    last_e2e: str = ""
    infer_ms_samples: list[float] = field(default_factory=list)
    approach_ms_samples: list[float] = field(default_factory=list)
    motion_window_fps_samples: list[float] = field(default_factory=list)


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
    parser = argparse.ArgumentParser(description="AT-3.4: Live approach + motion + kNN classification bench.")
    parser.add_argument("--phase-seconds", type=int, default=DEFAULT_PHASE_SECONDS)
    parser.add_argument("--show-window", action="store_true")
    parser.add_argument("--write-status", action="store_true")
    parser.add_argument("--log-dir", type=Path, default=SCRIPT_DIR / "logs")
    parser.add_argument("--run-data-dir", type=Path, default=SCRIPT_DIR / "run_data")
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    return parser.parse_args()


def _bootstrap_analysis_lib() -> None:
    lib_str = str(BATCH_LIB)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)


def _resolve_first(candidates: tuple[Path, ...], label: str) -> Path:
    for path in candidates:
        if path.is_file():
            return path
    joined = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"{label} not found. Tried: {joined}")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_configs(config_dir: Path):
    from at_3_4_pipeline import DEFAULT_DETECTOR_SCORE_THRESHOLD, DEFAULT_MIN_BOX_CENTER_X
    from motion_score_series import motion_config_from_dict
    from stop_sign_approach_pattern import ApproachDropConfig

    approach_raw = _load_json(config_dir / "approach_config.json")
    fields = {name for name in ApproachDropConfig.__dataclass_fields__}
    approach_config = ApproachDropConfig(
        **{key: value for key, value in approach_raw.items() if key in fields}
    )
    motion_config = motion_config_from_dict(_load_json(config_dir / "motion_config.json"))
    metrics_config = _load_json(config_dir / "metrics_config.json")
    knn_config = _load_json(config_dir / "knn_config.json")
    detector_path = config_dir / "detector_config.json"
    detector_raw = _load_json(detector_path) if detector_path.is_file() else {}
    post_drop_window_s = float(metrics_config["post_drop_window_s"])
    k_neighbors = int(knn_config["k_neighbors"])
    score_threshold = float(detector_raw.get("score_threshold", DEFAULT_DETECTOR_SCORE_THRESHOLD))
    min_box_center_x = float(detector_raw.get("min_box_center_x", DEFAULT_MIN_BOX_CENTER_X))
    return (
        approach_config,
        motion_config,
        post_drop_window_s,
        k_neighbors,
        score_threshold,
        min_box_center_x,
    )


def _load_knn_pipelines(config_dir: Path):
    try:
        import joblib
    except ImportError as exc:
        raise SystemExit("joblib is required on the Pi: pip install joblib scikit-learn") from exc

    stage1_path = config_dir / "knn_stage1.joblib"
    stage2_path = config_dir / "knn_stage2.joblib"
    if not stage1_path.is_file():
        raise FileNotFoundError(
            f"Missing {stage1_path.name}. Run prepare_at_3_4_config.py on a laptop first."
        )
    stage1 = joblib.load(stage1_path)
    stage2 = joblib.load(stage2_path) if stage2_path.is_file() else None
    return stage1, stage2


def _load_labels(path: Path) -> dict[int, str]:
    labels: dict[int, str] = {}
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        text = line.strip()
        if not text:
            continue
        parts = text.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            labels[int(parts[0])] = parts[1]
        else:
            labels[index] = text
    return labels


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def _avg_ms(values: list[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


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


def _classification_banner_bgr(stage1_predicted: str) -> tuple[int, int, int]:
    if stage1_predicted == "complete-stop":
        return (255, 128, 0)
    return (0, 0, 220)


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


def _draw_overlay(
    frame_bgr: np.ndarray,
    *,
    phase_header: str,
    lap_count: int,
    loop_fps: float,
    area_series_len: int,
    max_area_pct: float,
    infer_ms_avg: float,
    approach_ms_avg: float,
    cycle: ApproachCycle | None,
    banners_visible: bool,
) -> None:
    cv2.putText(
        frame_bgr,
        phase_header,
        (10, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.95,
        (255, 255, 255),
        4,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame_bgr,
        phase_header,
        (10, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.95,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )

    hud_y = 68
    for line in (
        f"laps={lap_count} loop_fps={loop_fps:.2f} infer_ms={infer_ms_avg:.1f}",
        f"area_len={area_series_len} max_area={max_area_pct:.2f}% approach_ms={approach_ms_avg:.1f}",
    ):
        cv2.putText(
            frame_bgr,
            line,
            (10, hud_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        hud_y += 24

    if not banners_visible or cycle is None:
        return

    banner_top = 120
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


def _wait_for_phase_start(
    *,
    phase_header: str,
    cap: cv2.VideoCapture,
    show_window: bool,
) -> None:
    message = f"{phase_header} — press SPACE to start"
    print(message, flush=True)
    if not show_window:
        input("Press Enter to start phase...")
        return

    preview_size: tuple[int, int] | None = None
    cv2.namedWindow(PREVIEW_WINDOW, cv2.WINDOW_NORMAL)
    while True:
        ok, frame_bgr = cap.read()
        if not ok or frame_bgr is None:
            frame_bgr = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            frame_bgr = frame_bgr.copy()

        if preview_size is None:
            preview_size = _preview_size(frame_bgr.shape[1], frame_bgr.shape[0])
            cv2.resizeWindow(PREVIEW_WINDOW, preview_size[0], preview_size[1])

        overlay = frame_bgr.copy()
        cv2.putText(
            overlay,
            phase_header,
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            overlay,
            "Press SPACE to start",
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(PREVIEW_WINDOW, _frame_for_preview(overlay, preview_size))
        key = cv2.waitKey(30) & 0xFF
        if key == ord(" "):
            break
        if key in (ord("q"), 27):
            raise KeyboardInterrupt("quit during phase wait")


def _append_event(events: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    events.append(payload)


def _log_run_start(
    *,
    config_dir: Path,
    model_path: Path,
    post_drop_window_s: float,
    phase_seconds: int,
    run_stamp: str,
    log_dir: Path,
    run_data_dir: Path,
) -> None:
    print("\n=== AT-3.4 live bench starting ===", flush=True)
    print(f"  run_stamp: {run_stamp}", flush=True)
    print(f"  config_dir: {config_dir}", flush=True)
    print(f"  post_drop_window_s: {post_drop_window_s}", flush=True)
    print(f"  phase_seconds: {phase_seconds}", flush=True)
    print(f"  banner_dwell_s: {BANNER_DWELL_S}", flush=True)
    print(f"  model: {model_path}", flush=True)
    print(f"  logs: {log_dir}", flush=True)
    print(f"  run_data: {run_data_dir / run_stamp}", flush=True)
    print("  phases: 1=baseline, 2=complete-stop, 3=rolling, 4=run-through", flush=True)


def _log_phase_start(phase_spec: dict[str, Any], *, phase_seconds: int) -> None:
    phase_num = int(phase_spec["phase"])
    header = str(phase_spec["header"])
    motion = bool(phase_spec["motion_enabled"])
    classify = bool(phase_spec["classify_enabled"])
    print(f"\n>>> Phase {phase_num} armed: {header}", flush=True)
    print(
        f"    motion={motion} classify={classify} duration={phase_seconds}s — press SPACE to begin",
        flush=True,
    )


def _log_phase_end(result: PhaseResult) -> None:
    short_title = result.title.split("—", 1)[-1].strip() if "—" in result.title else result.title
    print(f"\n--- Phase {result.phase} ended: {short_title} ---", flush=True)
    print(
        f"  duration={result.duration_s:.1f}s laps={result.lap_count} loop_fps={result.loop_fps:.2f}",
        flush=True,
    )
    print(
        f"  infer_ms_avg={result.infer_ms_avg:.1f} "
        f"approach_ms_avg={result.approach_ms_avg:.1f} "
        f"approach_ms_p95={result.approach_ms_p95:.1f}",
        flush=True,
    )
    print(
        f"  approach: detected={result.approach_detected} count={result.approach_count}",
        flush=True,
    )
    print(
        f"  classification: fired={result.classification_fired} count={result.classification_count}",
        flush=True,
    )
    if result.classification_fired and result.last_stage1:
        print(
            f"  last_prediction: stage1={result.last_stage1} e2e={result.last_e2e or '?'}",
            flush=True,
        )
    if result.motion_window_fps_avg is not None:
        print(f"  motion_window_fps_avg={result.motion_window_fps_avg:.2f}", flush=True)
    if result.motion_window_fps_min is not None:
        print(f"  motion_window_fps_min={result.motion_window_fps_min:.2f} (diagnostic)", flush=True)
    if result.phase == 1:
        print("  (baseline FPS reference for phases 2–4)", flush=True)
    elif result.approach_count != 1 or result.classification_count != 1:
        print(
            "  WARN: phase 2–4 should log exactly one approach and one classification",
            flush=True,
        )
    elif not result.approach_detected or not result.classification_fired:
        print("  WARN: phase 2–4 should log both approach and classification", flush=True)
    print("---\n", flush=True)


def _run_phase(
    *,
    phase_spec: dict[str, Any],
    duration_seconds: float,
    cap: cv2.VideoCapture,
    interpreter: Any,
    input_details: list,
    output_details: list,
    input_dtype: Any,
    input_w: int,
    input_h: int,
    labels: dict[int, str],
    approach_config,
    motion_config,
    post_drop_window_s: float,
    stage1_pipeline,
    stage2_pipeline,
    score_threshold: float,
    min_box_center_x: float,
    show_window: bool,
    preview_size: tuple[int, int] | None,
    events: list[dict[str, Any]],
) -> PhaseResult:
    from per_frame_approach_sim import PerFrameConfig, detect_approach_per_frame

    phase_num = int(phase_spec["phase"])
    header = str(phase_spec["header"])
    motion_enabled = bool(phase_spec["motion_enabled"])
    classify_enabled = bool(phase_spec["classify_enabled"])

    _append_event(
        events,
        {"event": "phase_start", "phase": phase_num, "title": header.split("—", 1)[-1].strip(), "t": 0.0},
    )
    print(f"[phase {phase_num}] running ({duration_seconds:.0f}s)...", flush=True)

    result = PhaseResult(phase=phase_num, title=header)
    area_series: list[float] = []
    max_area_pct = 0.0
    motion_tracker = LiveMotionTracker(motion_config)
    per_frame_config = PerFrameConfig(post_drop_window_s=post_drop_window_s)

    active_cycle: ApproachCycle | None = None
    banners_visible = False
    cycle_locked = False
    single_cycle_phase = classify_enabled
    last_lap_end = time.perf_counter()

    start = time.perf_counter()
    deadline = start + duration_seconds

    while True:
        now = time.perf_counter()
        if now >= deadline:
            break

        ok, frame_bgr = cap.read()
        if not ok or frame_bgr is None:
            print(f"WARN [phase {phase_num}]: failed to read camera frame")
            continue

        elapsed = now - start
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(frame_rgb, (int(input_w), int(input_h)))
        input_tensor = np.expand_dims(resized, axis=0).astype(input_dtype)

        infer_t0 = time.perf_counter()
        interpreter.set_tensor(input_details[0]["index"], input_tensor)
        interpreter.invoke()
        boxes = interpreter.get_tensor(output_details[0]["index"])[0]
        classes = interpreter.get_tensor(output_details[1]["index"])[0]
        scores = interpreter.get_tensor(output_details[2]["index"])[0]
        count = int(interpreter.get_tensor(output_details[3]["index"])[0])
        infer_ms = (time.perf_counter() - infer_t0) * 1000.0
        result.infer_ms_samples.append(infer_ms)

        area_fraction = max_stop_sign_area_fraction(
            boxes=boxes,
            classes=classes,
            scores=scores,
            count=count,
            labels=labels,
            score_threshold=score_threshold,
            min_box_center_x=min_box_center_x,
        )

        track_approach = active_cycle is None and not cycle_locked
        detect_time_s: float | None = None
        if track_approach:
            area_series.append(area_fraction)
            max_area_pct = max(max_area_pct, area_fraction * 100.0)

            approach_t0 = time.perf_counter()
            _detect_frame, detect_time_s = detect_approach_per_frame(
                area_series,
                max(result.lap_count + 1, 1) / elapsed if elapsed > 0 else 30.0,
                approach_config=approach_config,
                per_frame_config=per_frame_config,
            )
            result.approach_ms_samples.append((time.perf_counter() - approach_t0) * 1000.0)

        if (
            motion_enabled
            and classify_enabled
            and track_approach
            and detect_time_s is not None
        ):
            active_cycle = arm_approach_cycle(
                elapsed_s=elapsed,
                area_series=area_series,
                area_fraction=area_fraction,
            )
            banners_visible = True
            result.approach_detected = True
            result.approach_count += 1
            _append_event(
                events,
                {
                    "event": "approach_detected",
                    "phase": phase_num,
                    "t0_s": round(elapsed, 3),
                    "detect_frame": active_cycle.detect_frame,
                    "area_at_detect": round(area_fraction, 5),
                },
            )
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] *** APPROACH @ t={elapsed:.2f}s ({header}) ***", flush=True)

        in_motion_window = False
        if active_cycle is not None and motion_enabled:
            window_end = active_cycle.t0_s + post_drop_window_s
            in_motion_window = active_cycle.t0_s <= elapsed <= window_end
            if in_motion_window:
                raw = motion_tracker.score(frame_bgr)
                active_cycle.motion_raw.append(raw)
                smoothed = motion_tracker.smoothed(active_cycle.motion_raw)
                active_cycle.motion_samples.append((elapsed, smoothed))

            if (
                classify_enabled
                and not active_cycle.classified
                and elapsed >= window_end
                and active_cycle.motion_samples
            ):
                estimate_fps = max(result.lap_count + 1, 1) / elapsed if elapsed > 0 else 30.0
                prediction = classify_approach_cycle(
                    active_cycle,
                    approach_config=approach_config,
                    motion_config=motion_config,
                    post_drop_window_s=post_drop_window_s,
                    stage1_pipeline=stage1_pipeline,
                    stage2_pipeline=stage2_pipeline,
                    fps=estimate_fps,
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
                    result.classification_fired = True
                    result.classification_count += 1
                    result.last_stage1 = active_cycle.stage1_predicted
                    result.last_e2e = active_cycle.e2e_predicted
                    if single_cycle_phase:
                        cycle_locked = True
                        lock_cycle_buffers(
                            area_series=area_series,
                            motion_tracker=motion_tracker,
                        )
                    _append_event(
                        events,
                        {
                            "event": "classification",
                            "phase": phase_num,
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
                        f"[{datetime.now().strftime('%H:%M:%S')}] CLASSIFICATION: "
                        f"{active_cycle.stage1_predicted} / e2e={active_cycle.e2e_predicted}",
                        flush=True,
                    )

            if (
                active_cycle.banners_clear_at_s is not None
                and elapsed >= active_cycle.banners_clear_at_s
            ):
                _append_event(
                    events,
                    {"event": "banners_cleared", "phase": phase_num, "at_s": round(elapsed, 3)},
                )
                active_cycle = None
                banners_visible = False

        if motion_enabled and active_cycle is None and not cycle_locked:
            motion_tracker.prime_gray(frame_bgr)

        lap_end = time.perf_counter()
        lap_dt = lap_end - last_lap_end
        last_lap_end = lap_end
        if in_motion_window and lap_dt > 0:
            lap_fps = 1.0 / lap_dt
            result.motion_window_fps_samples.append(lap_fps)

        result.lap_count += 1
        loop_fps = result.lap_count / elapsed if elapsed > 0 else 0.0

        if show_window and preview_size is not None:
            display = frame_bgr.copy()
            _draw_overlay(
                display,
                phase_header=header,
                lap_count=result.lap_count,
                loop_fps=loop_fps,
                area_series_len=len(area_series),
                max_area_pct=max_area_pct,
                infer_ms_avg=_avg_ms(result.infer_ms_samples),
                approach_ms_avg=_avg_ms(result.approach_ms_samples),
                cycle=active_cycle if banners_visible else None,
                banners_visible=banners_visible,
            )
            cv2.imshow(PREVIEW_WINDOW, _frame_for_preview(display, preview_size))
            if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                print(f"WARN [phase {phase_num}]: quit early")
                break

    result.duration_s = time.perf_counter() - start
    result.loop_fps = result.lap_count / result.duration_s if result.duration_s > 0 else 0.0
    result.infer_ms_avg = _avg_ms(result.infer_ms_samples)
    result.approach_ms_avg = _avg_ms(result.approach_ms_samples)
    result.approach_ms_p95 = _percentile(result.approach_ms_samples, 95.0)
    if result.motion_window_fps_samples:
        result.motion_window_fps_min = min(result.motion_window_fps_samples)
        result.motion_window_fps_avg = sum(result.motion_window_fps_samples) / len(
            result.motion_window_fps_samples
        )

    _append_event(
        events,
        {
            "event": "phase_end",
            "phase": phase_num,
            "duration_s": round(result.duration_s, 3),
            "lap_count": result.lap_count,
            "loop_fps": round(result.loop_fps, 3),
            "infer_ms_avg": round(result.infer_ms_avg, 2),
            "approach_ms_p95": round(result.approach_ms_p95, 2),
            "approach_count": result.approach_count,
            "classification_count": result.classification_count,
            "approach_detected": result.approach_detected,
            "classification_fired": result.classification_fired,
            "last_stage1": result.last_stage1,
            "last_e2e": result.last_e2e,
            "motion_window_fps_avg": result.motion_window_fps_avg,
            "motion_window_fps_min": result.motion_window_fps_min,
        },
    )
    _log_phase_end(result)
    return result


def _write_run_data(run_dir: Path, events: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (run_dir / "events.jsonl").open("w", encoding="utf-8") as handle:
        for item in events:
            handle.write(json.dumps(item) + "\n")


def _write_summary(
    *,
    log_dir: Path,
    run_stamp: str,
    baseline: PhaseResult,
    stop_phases: list[PhaseResult],
    write_status: bool,
) -> dict[str, Any]:
    baseline_fps = baseline.loop_fps
    # Pass on average motion-window FPS (ignore single-lap dips that tank min).
    motion_fps_avgs = [
        phase.motion_window_fps_avg
        for phase in stop_phases
        if phase.motion_window_fps_avg is not None
    ]
    motion_fps_mins = [
        phase.motion_window_fps_min
        for phase in stop_phases
        if phase.motion_window_fps_min is not None
    ]
    worst_motion_avg_fps = min(motion_fps_avgs) if motion_fps_avgs else None
    worst_motion_min_fps = min(motion_fps_mins) if motion_fps_mins else None
    fps_delta_pct = None
    pass_motion_fps = True
    if baseline_fps > 0 and worst_motion_avg_fps is not None:
        fps_delta_pct = (baseline_fps - worst_motion_avg_fps) / baseline_fps * 100.0
        pass_motion_fps = fps_delta_pct <= PASS_FPS_DELTA_PCT

    approach_ms_all = [
        sample for phase in stop_phases for sample in phase.approach_ms_samples
    ]
    approach_ms_p95 = _percentile(approach_ms_all, 95.0)
    pass_approach_ms = approach_ms_p95 <= PASS_APPROACH_MS_P95 or not approach_ms_all

    pass_stop_phases = all(
        phase.approach_detected
        and phase.classification_fired
        and phase.approach_count == 1
        and phase.classification_count == 1
        for phase in stop_phases
    )
    overall_pass = pass_motion_fps and pass_approach_ms and pass_stop_phases

    phase_summaries = []
    for phase in [baseline, *stop_phases]:
        phase_summaries.append(
            {
                "phase": phase.phase,
                "title": phase.title,
                "loop_fps": round(phase.loop_fps, 3),
                "approach_detected": phase.approach_detected,
                "classification_fired": phase.classification_fired,
                "approach_count": phase.approach_count,
                "classification_count": phase.classification_count,
                "motion_window_fps_avg": (
                    round(phase.motion_window_fps_avg, 3)
                    if phase.motion_window_fps_avg is not None
                    else None
                ),
                "motion_window_fps_min": (
                    round(phase.motion_window_fps_min, 3)
                    if phase.motion_window_fps_min is not None
                    else None
                ),
            }
        )

    summary: dict[str, Any] = {
        "run_stamp": run_stamp,
        "baseline_fps": round(baseline_fps, 3),
        "worst_motion_window_fps_avg": (
            round(worst_motion_avg_fps, 3) if worst_motion_avg_fps is not None else None
        ),
        "worst_motion_window_fps_min": (
            round(worst_motion_min_fps, 3) if worst_motion_min_fps is not None else None
        ),
        "fps_delta_pct_vs_baseline": round(fps_delta_pct, 2) if fps_delta_pct is not None else None,
        "approach_ms_p95": round(approach_ms_p95, 2),
        "pass_motion_fps": pass_motion_fps,
        "pass_approach_ms_p95": pass_approach_ms,
        "pass_stop_phase_events": pass_stop_phases,
        "pass_overall_heuristic": overall_pass,
        "phases": phase_summaries,
    }

    summary_path = log_dir / f"{LOG_PREFIX}_summary_{run_stamp}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if write_status:
        (log_dir / "last_bench_status.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== AT-3.4 summary ===")
    for key, value in summary.items():
        if key != "phases":
            print(f"  {key}: {value}")
    print(
        f"\nPass criteria: motion-window avg fps_delta <= {PASS_FPS_DELTA_PCT}% "
        f"(vs baseline; min FPS logged only), "
        f"approach_ms_p95 <= {PASS_APPROACH_MS_P95}ms, "
        f"phases 2-4 exactly one approach and one classification each"
    )
    print(f"Result: {'PASS' if overall_pass else 'FAIL'}")
    print(f"Summary written: {summary_path}")
    return summary


def main() -> int:
    args = parse_args()
    config_dir = args.config_dir.resolve()
    args.log_dir.mkdir(parents=True, exist_ok=True)

    _bootstrap_analysis_lib()
    (
        approach_config,
        motion_config,
        post_drop_window_s,
        _k,
        score_threshold,
        min_box_center_x,
    ) = _load_configs(config_dir)
    stage1_pipeline, stage2_pipeline = _load_knn_pipelines(config_dir)

    model_path = _resolve_first(MODEL_CANDIDATES, "Edge TPU model")
    label_path = _resolve_first(LABEL_CANDIDATES, "COCO labels")
    labels = _load_labels(label_path)

    print("Loading Edge TPU interpreter...")
    interpreter = tflite.Interpreter(
        model_path=str(model_path),
        experimental_delegates=[tflite.load_delegate("libedgetpu.so.1")],
    )
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    _, input_h, input_w, input_c = input_details[0]["shape"]
    input_dtype = input_details[0]["dtype"]
    if input_c != 3:
        raise ValueError(f"Expected 3 input channels, got {input_c}")

    print(f"Opening USB camera at index {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open USB camera at index {CAMERA_INDEX}")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    preview_size: tuple[int, int] | None = None
    if args.show_window:
        ok, probe = cap.read()
        if ok and probe is not None:
            preview_size = _preview_size(probe.shape[1], probe.shape[0])
            cv2.namedWindow(PREVIEW_WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(PREVIEW_WINDOW, preview_size[0], preview_size[1])

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.run_data_dir / run_stamp
    events: list[dict[str, Any]] = []
    phase_results: list[PhaseResult] = []

    _log_run_start(
        config_dir=config_dir,
        model_path=model_path,
        post_drop_window_s=post_drop_window_s,
        phase_seconds=args.phase_seconds,
        run_stamp=run_stamp,
        log_dir=args.log_dir,
        run_data_dir=args.run_data_dir,
    )

    provenance_path = config_dir / "provenance.json"
    manifest = {
        "run_stamp": run_stamp,
        "phase_seconds": args.phase_seconds,
        "post_drop_window_s": post_drop_window_s,
        "banner_dwell_s": BANNER_DWELL_S,
        "provenance": json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance_path.is_file()
        else {},
    }

    try:
        for phase_spec in PHASES:
            _log_phase_start(phase_spec, phase_seconds=args.phase_seconds)
            _wait_for_phase_start(phase_header=str(phase_spec["header"]), cap=cap, show_window=args.show_window)
            phase_result = _run_phase(
                phase_spec=phase_spec,
                duration_seconds=float(args.phase_seconds),
                cap=cap,
                interpreter=interpreter,
                input_details=input_details,
                output_details=output_details,
                input_dtype=input_dtype,
                input_w=input_w,
                input_h=input_h,
                labels=labels,
                approach_config=approach_config,
                motion_config=motion_config,
                post_drop_window_s=post_drop_window_s,
                stage1_pipeline=stage1_pipeline,
                stage2_pipeline=stage2_pipeline,
                score_threshold=score_threshold,
                min_box_center_x=min_box_center_x,
                show_window=args.show_window,
                preview_size=preview_size,
                events=events,
            )
            phase_results.append(phase_result)
    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)
        return 1
    finally:
        cap.release()
        if args.show_window:
            cv2.destroyAllWindows()

    if not phase_results:
        print("No phases completed.", flush=True)
        return 1

    print("\n=== All phases complete — writing artifacts ===", flush=True)
    _write_run_data(run_dir, events, manifest)
    baseline = phase_results[0]
    stop_phases = phase_results[1:]
    summary = _write_summary(
        log_dir=args.log_dir,
        run_stamp=run_stamp,
        baseline=baseline,
        stop_phases=stop_phases,
        write_status=args.write_status,
    )
    print(f"Run data: {run_dir / 'events.jsonl'}")
    return 0 if summary["pass_overall_heuristic"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
