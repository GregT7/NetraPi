"""
AT-3.3: Continuous approach live benchmark (Pi FPS + overlay).

Measures loop FPS with vs without one diagnose_approach_drop call per lap on the
growing area series. HDMI overlay shows APPROACH DETECTED in the car.

Usage (from repo root, Pi with camera + Coral):

    python src/tests/integration/at_3_3/at_3_3_continuous_approach_live_benchmark.py \\
        --duration-seconds 120 --show-window --write-status
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
REPO_ROOT = SCRIPT_DIR.parents[2]
BATCH_LIB = REPO_ROOT / "src" / "tests" / "analysis" / "batch_analysis" / "scripts" / "lib"
DEFAULT_APPROACH_CONFIG = (
    REPO_ROOT
    / "src/tests/analysis/batch_analysis/evaluation/motion_area_1/config/approach_config.json"
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
SCORE_THRESHOLD = 0.45
STOP_SIGN_LABEL = "stop sign"
DEFAULT_PHASE_SECONDS = 60
SNAPSHOT_COUNT = 6
PREVIEW_WINDOW = "AT-3.3 Continuous Approach Bench"
PASS_FPS_DELTA_PCT = 33.0
PASS_APPROACH_MS_P95 = 33.0
LOG_PREFIX = "at_3_3"


@dataclass
class PhaseMetrics:
    phase_name: str
    duration_s: float = 0.0
    lap_count: int = 0
    loop_fps: float = 0.0
    infer_ms_avg: float = 0.0
    approach_ms_avg: float = 0.0
    approach_ms_p95: float = 0.0
    approach_detected: bool = False
    first_detect_time_s: float | None = None
    infer_ms_samples: list[float] = field(default_factory=list)
    approach_ms_samples: list[float] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AT-3.3: Benchmark loop FPS with vs without continuous approach detection."
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=DEFAULT_PHASE_SECONDS * 2,
        help=f"Total run time; split evenly between baseline and approach phases (default {DEFAULT_PHASE_SECONDS * 2}).",
    )
    parser.add_argument(
        "--phase-seconds",
        type=int,
        default=DEFAULT_PHASE_SECONDS,
        help="Override per-phase duration (uses half of --duration-seconds when omitted).",
    )
    parser.add_argument(
        "--show-window",
        action="store_true",
        help="HDMI preview with loop stats and APPROACH DETECTED overlay.",
    )
    parser.add_argument(
        "--write-status",
        action="store_true",
        help="Write logs/last_bench_status.json after the run.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=SCRIPT_DIR / "logs",
        help="Directory for CSV metrics and optional status JSON.",
    )
    parser.add_argument(
        "--approach-config",
        type=Path,
        default=DEFAULT_APPROACH_CONFIG,
        help="approach_config.json path (min_peak_pct overridden to 0.25 / pf_02).",
    )
    parser.add_argument(
        "--replay-areas",
        type=Path,
        help="Dev only: replay a *.areas.json file (approach timing sanity check, not a Pi FPS benchmark).",
    )
    return parser.parse_args()


def _resolve_first(candidates: tuple[Path, ...], label: str) -> Path:
    for path in candidates:
        if path.is_file():
            return path
    joined = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"{label} not found. Tried: {joined}")


def _bootstrap_analysis_lib() -> None:
    lib_str = str(BATCH_LIB)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)


def _load_approach_config(path: Path):
    from stop_sign_approach_pattern import ApproachDropConfig

    raw = json.loads(path.read_text(encoding="utf-8"))
    fields = {name for name in ApproachDropConfig.__dataclass_fields__}
    kwargs = {key: value for key, value in raw.items() if key in fields}
    kwargs["min_peak_pct"] = 0.25
    return ApproachDropConfig(**kwargs)


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
    return (sum(values) / len(values) * 1000.0) if values else 0.0


def _max_stop_sign_area_fraction(
    *,
    boxes: np.ndarray,
    classes: np.ndarray,
    scores: np.ndarray,
    count: int,
    labels: dict[int, str],
) -> float:
    best = 0.0
    limit = min(count, len(scores))
    for index in range(limit):
        score = float(scores[index])
        if score < SCORE_THRESHOLD:
            continue
        class_id = int(classes[index])
        label = labels.get(class_id, "").strip().lower()
        if label != STOP_SIGN_LABEL:
            continue
        ymin, xmin, ymax, xmax = boxes[index]
        width = max(0.0, float(xmax) - float(xmin))
        height = max(0.0, float(ymax) - float(ymin))
        best = max(best, width * height)
    return best


def _draw_overlay(
    frame_bgr: np.ndarray,
    *,
    phase_label: str,
    lap_count: int,
    loop_fps: float,
    area_series_len: int,
    max_area_pct: float,
    approach_detected: bool,
    first_detect_time_s: float | None,
) -> None:
    lines = [
        f"{phase_label} laps={lap_count} loop_fps={loop_fps:.2f}",
        f"area_len={area_series_len} max_area={max_area_pct:.2f}%",
    ]
    y = 28
    for line in lines:
        cv2.putText(
            frame_bgr,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        y += 28

    if approach_detected and first_detect_time_s is not None:
        banner = f"APPROACH DETECTED @ t={first_detect_time_s:.1f}s"
        cv2.rectangle(frame_bgr, (0, 60), (frame_bgr.shape[1], 120), (0, 180, 0), -1)
        cv2.putText(
            frame_bgr,
            banner,
            (10, 105),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )


def _run_phase(
    *,
    phase_name: str,
    duration_seconds: float,
    with_approach: bool,
    cap: cv2.VideoCapture,
    interpreter: Any,
    input_details: list,
    output_details: list,
    input_dtype: Any,
    input_w: int,
    input_h: int,
    labels: dict[int, str],
    approach_config,
    show_window: bool,
    log_handle,
    phase_start_offset: float,
) -> PhaseMetrics:
    from stop_sign_approach_pattern import diagnose_approach_drop

    metrics = PhaseMetrics(phase_name=phase_name)
    area_series: list[float] = []
    approach_detected = False
    first_detect_time_s: float | None = None
    max_area_pct = 0.0

    start = time.perf_counter()
    deadline = start + duration_seconds
    snapshot_interval = duration_seconds / SNAPSHOT_COUNT if duration_seconds > 0 else 0.0
    next_snapshot = start + snapshot_interval if snapshot_interval > 0 else None
    snapshot_index = 0

    while True:
        now = time.perf_counter()
        if now >= deadline:
            break

        ok, frame_bgr = cap.read()
        if not ok or frame_bgr is None:
            print(f"WARN [{phase_name}]: failed to read camera frame")
            continue

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
        metrics.infer_ms_samples.append(infer_ms)

        area_fraction = _max_stop_sign_area_fraction(
            boxes=boxes,
            classes=classes,
            scores=scores,
            count=count,
            labels=labels,
        )
        area_series.append(area_fraction)
        max_area_pct = max(max_area_pct, area_fraction * 100.0)

        if with_approach and area_series:
            elapsed = time.perf_counter() - start
            fps = max(metrics.lap_count + 1, 1) / elapsed if elapsed > 0 else 30.0
            approach_t0 = time.perf_counter()
            diagnosis = diagnose_approach_drop(area_series, fps, config=approach_config)
            metrics.approach_ms_samples.append((time.perf_counter() - approach_t0) * 1000.0)
            if diagnosis is not None and diagnosis.event is not None and not approach_detected:
                approach_detected = True
                first_detect_time_s = elapsed
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] *** APPROACH DETECTED @ t={first_detect_time_s:.2f}s ({phase_name}) ***")

        metrics.lap_count += 1
        lap_end = time.perf_counter()
        elapsed = lap_end - start
        loop_fps = metrics.lap_count / elapsed if elapsed > 0 else 0.0

        while next_snapshot is not None and snapshot_index < SNAPSHOT_COUNT and lap_end >= next_snapshot:
            snapshot_index += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_handle.write(
                f"{timestamp},snapshot,{phase_name},{snapshot_index},{elapsed:.3f},"
                f"{metrics.lap_count},{loop_fps:.3f},{_avg_ms(metrics.infer_ms_samples):.3f},"
                f"{_avg_ms(metrics.approach_ms_samples):.3f},{int(approach_detected)}\n"
            )
            log_handle.flush()
            print(
                f"[{timestamp}] {phase_name} snapshot {snapshot_index}/{SNAPSHOT_COUNT} "
                f"lap_fps={loop_fps:.2f} infer_ms={_avg_ms(metrics.infer_ms_samples):.1f} "
                f"approach_ms={_avg_ms(metrics.approach_ms_samples):.1f}"
            )
            next_snapshot += snapshot_interval

        if show_window:
            _draw_overlay(
                frame_bgr,
                phase_label=phase_name,
                lap_count=metrics.lap_count,
                loop_fps=loop_fps,
                area_series_len=len(area_series),
                max_area_pct=max_area_pct,
                approach_detected=approach_detected,
                first_detect_time_s=first_detect_time_s,
            )
            cv2.imshow(PREVIEW_WINDOW, frame_bgr)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                print(f"WARN [{phase_name}]: quit early with 'q'")
                break

    metrics.duration_s = time.perf_counter() - start
    metrics.loop_fps = metrics.lap_count / metrics.duration_s if metrics.duration_s > 0 else 0.0
    metrics.infer_ms_avg = _avg_ms(metrics.infer_ms_samples)
    metrics.approach_ms_avg = _avg_ms(metrics.approach_ms_samples)
    metrics.approach_ms_p95 = _percentile(metrics.approach_ms_samples, 95.0)
    metrics.approach_detected = approach_detected
    metrics.first_detect_time_s = first_detect_time_s
    _ = phase_start_offset
    return metrics


def _run_replay(areas_path: Path, approach_config_path: Path) -> int:
    _bootstrap_analysis_lib()
    from area_series_cache import load_areas_from_processed_file
    from stop_sign_approach_pattern import diagnose_approach_drop

    loaded = load_areas_from_processed_file(areas_path)
    if loaded is None:
        print(f"Could not load areas file: {areas_path}", file=sys.stderr)
        return 1

    areas, fps, clip_name = loaded
    approach_config = _load_approach_config(approach_config_path)
    area_series: list[float] = []
    first_detect_frame: int | None = None
    approach_ms_samples: list[float] = []

    print(f"REPLAY MODE (not a Pi FPS benchmark): {clip_name} @ {fps:.2f} fps, {len(areas)} frames")
    replay_start = time.perf_counter()
    for index, area in enumerate(areas):
        area_series.append(area)
        t0 = time.perf_counter()
        diagnosis = diagnose_approach_drop(area_series, fps, config=approach_config)
        approach_ms_samples.append((time.perf_counter() - t0) * 1000.0)
        if diagnosis is not None and diagnosis.event is not None and first_detect_frame is None:
            first_detect_frame = index

    elapsed = time.perf_counter() - replay_start
    detected = first_detect_frame is not None
    print(
        f"approach_detected={'yes' if detected else 'no'} "
        f"first_frame={first_detect_frame + 1 if first_detect_frame is not None else 'n/a'} "
        f"approach_ms_avg={_avg_ms(approach_ms_samples):.2f} "
        f"approach_ms_p95={_percentile(approach_ms_samples, 95.0):.2f} "
        f"replay_wall_s={elapsed:.2f}"
    )
    return 0 if detected else 1


def _write_summary(
    *,
    log_dir: Path,
    run_stamp: str,
    baseline: PhaseMetrics,
    approach: PhaseMetrics,
    write_status: bool,
) -> dict[str, Any]:
    fps_delta = baseline.loop_fps - approach.loop_fps
    fps_delta_pct = (fps_delta / baseline.loop_fps * 100.0) if baseline.loop_fps > 0 else 0.0
    pass_fps = fps_delta_pct <= PASS_FPS_DELTA_PCT
    pass_approach_ms = approach.approach_ms_p95 <= PASS_APPROACH_MS_P95 or not approach.approach_ms_samples
    pass_approach_detected = approach.approach_detected
    overall_pass = pass_fps and pass_approach_ms and pass_approach_detected

    summary = {
        "run_stamp": run_stamp,
        "loop_fps_baseline": round(baseline.loop_fps, 3),
        "loop_fps_approach": round(approach.loop_fps, 3),
        "fps_delta": round(fps_delta, 3),
        "fps_delta_pct": round(fps_delta_pct, 2),
        "infer_ms_avg_baseline": round(baseline.infer_ms_avg, 2),
        "infer_ms_avg_approach": round(approach.infer_ms_avg, 2),
        "approach_ms_avg": round(approach.approach_ms_avg, 2),
        "approach_ms_p95": round(approach.approach_ms_p95, 2),
        "approach_detected": approach.approach_detected,
        "first_detect_time_s": approach.first_detect_time_s,
        "pass_fps_delta": pass_fps,
        "pass_approach_ms_p95": pass_approach_ms,
        "pass_approach_detected": pass_approach_detected,
        "pass_overall_heuristic": overall_pass,
    }

    summary_path = log_dir / f"{LOG_PREFIX}_summary_{run_stamp}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if write_status:
        status_path = log_dir / "last_bench_status.json"
        status_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== AT-3.3 summary ===")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print(
        f"\nPass criteria: fps_delta_pct <= {PASS_FPS_DELTA_PCT}%, "
        f"approach_ms_p95 <= {PASS_APPROACH_MS_P95}ms, approach_detected = true"
    )
    print(f"Result: {'PASS' if overall_pass else 'FAIL'}")
    print(f"Summary written: {summary_path}")
    return summary


def main() -> int:
    args = parse_args()
    args.log_dir.mkdir(parents=True, exist_ok=True)

    if args.replay_areas is not None:
        return _run_replay(args.replay_areas.resolve(), args.approach_config.resolve())

    _bootstrap_analysis_lib()
    model_path = _resolve_first(MODEL_CANDIDATES, "Edge TPU model")
    label_path = _resolve_first(LABEL_CANDIDATES, "COCO labels")
    approach_config = _load_approach_config(args.approach_config.resolve())
    labels = _load_labels(label_path)

    phase_seconds = args.phase_seconds if args.phase_seconds > 0 else max(1, args.duration_seconds // 2)

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

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    metrics_log = args.log_dir / f"{LOG_PREFIX}_metrics_{run_stamp}.csv"
    log_handle = metrics_log.open("w", encoding="utf-8")
    log_handle.write(
        "timestamp,event,phase,snapshot,elapsed_s,lap_count,loop_fps,infer_ms_avg,approach_ms_avg,approach_detected\n"
    )

    try:
        print(f"Phase 1/2: baseline ({phase_seconds}s) — capture + infer + area, no approach")
        baseline = _run_phase(
            phase_name="baseline",
            duration_seconds=phase_seconds,
            with_approach=False,
            cap=cap,
            interpreter=interpreter,
            input_details=input_details,
            output_details=output_details,
            input_dtype=input_dtype,
            input_w=input_w,
            input_h=input_h,
            labels=labels,
            approach_config=approach_config,
            show_window=args.show_window,
            log_handle=log_handle,
            phase_start_offset=0.0,
        )

        print(f"Phase 2/2: with_approach ({phase_seconds}s) — + diagnose_approach_drop each lap")
        approach = _run_phase(
            phase_name="with_approach",
            duration_seconds=phase_seconds,
            with_approach=True,
            cap=cap,
            interpreter=interpreter,
            input_details=input_details,
            output_details=output_details,
            input_dtype=input_dtype,
            input_w=input_w,
            input_h=input_h,
            labels=labels,
            approach_config=approach_config,
            show_window=args.show_window,
            log_handle=log_handle,
            phase_start_offset=baseline.duration_s,
        )
    finally:
        cap.release()
        if args.show_window:
            cv2.destroyAllWindows()
        log_handle.close()

    summary = _write_summary(
        log_dir=args.log_dir,
        run_stamp=run_stamp,
        baseline=baseline,
        approach=approach,
        write_status=args.write_status,
    )
    print(f"Metrics log: {metrics_log}")
    return 0 if summary["pass_overall_heuristic"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
