import argparse
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite

CAMERA_INDEX = 0

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = REPO_ROOT / "src" / "models" / "ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite"

DEFAULT_DURATION_SECONDS = 10 * 60
DEFAULT_MAX_GAP_SECONDS = 5.0
SNAPSHOT_COUNT = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TP-12: Detection loop real-time operation test."
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=DEFAULT_DURATION_SECONDS,
        help="How long to run the loop. Default is 600 seconds (10 minutes).",
    )
    parser.add_argument(
        "--max-gap-seconds",
        type=float,
        default=DEFAULT_MAX_GAP_SECONDS,
        help="Fail if time between inferences exceeds this value.",
    )
    parser.add_argument(
        "--show-window",
        action="store_true",
        help="Display the live camera feed with loop stats.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "logs",
        help="Directory where TP-12 run logs are written.",
    )
    return parser.parse_args()


def write_metrics_snapshot(
    log_handle,
    snapshot_number: int,
    elapsed: float,
    frame_read_count: int,
    inference_count: int,
    last_gap_seconds: float,
    max_gap_seconds: float,
    status: str = "ok",
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    capture_fps = frame_read_count / elapsed if elapsed > 0 else 0.0
    inference_fps = inference_count / elapsed if elapsed > 0 else 0.0

    log_handle.write(
        f"{timestamp},periodic_metrics_{snapshot_number},{elapsed:.3f},{frame_read_count},"
        f"{capture_fps:.3f},{inference_count},{inference_fps:.3f},"
        f"{last_gap_seconds:.3f},{max_gap_seconds:.3f},{status}\n"
    )
    log_handle.flush()

    print(
        f"[{timestamp}] SNAPSHOT {snapshot_number}/{SNAPSHOT_COUNT} "
        f"elapsed={elapsed:.1f}s frames={frame_read_count} "
        f"capture_fps={capture_fps:.2f} inferences={inference_count} "
        f"infer_fps={inference_fps:.2f} last_gap={last_gap_seconds:.2f}s "
        f"max_gap={max_gap_seconds:.2f}s status={status}"
    )


def main() -> int:
    args = parse_args()

    model_file = Path(MODEL_PATH)
    if not model_file.exists():
        raise FileNotFoundError(f"Model not found: {model_file}")

    print("Loading interpreter...")
    interpreter = tflite.Interpreter(
        model_path=str(model_file),
        experimental_delegates=[tflite.load_delegate("libedgetpu.so.1")],
    )
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    _, input_h, input_w, input_c = input_details[0]["shape"]
    input_dtype = input_details[0]["dtype"]

    if input_c != 3:
        raise ValueError(f"Expected 3 input channels, got {input_c}")

    print(f"Opening USB camera at index {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open USB camera at index {CAMERA_INDEX}")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    start_time = time.perf_counter()
    deadline = start_time + args.duration_seconds
    snapshot_interval_seconds = (
        args.duration_seconds / SNAPSHOT_COUNT if args.duration_seconds > 0 else 0.0
    )
    next_snapshot_time = start_time + snapshot_interval_seconds if snapshot_interval_seconds > 0 else None
    snapshot_index = 0

    prev_inference_time = start_time
    inference_count = 0
    frame_read_count = 0
    stall_detected = False
    max_observed_gap_seconds = 0.0

    args.log_dir.mkdir(parents=True, exist_ok=True)
    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    metrics_log_file = args.log_dir / f"tp12_metrics_{run_stamp}.log"

    print(
        f"Starting TP-12 loop for {args.duration_seconds}s "
        f"(max inference gap {args.max_gap_seconds:.2f}s)"
    )
    if snapshot_interval_seconds > 0:
        print(
            f"Console + log: {SNAPSHOT_COUNT} metric snapshots, every "
            f"{snapshot_interval_seconds:.2f}s."
        )
    print("Press 'q' to stop early (counts as a failed test).")
    print(f"Metrics log file: {metrics_log_file}")

    log_handle = metrics_log_file.open("w", encoding="utf-8")
    log_handle.write(
        "timestamp,event,elapsed_s,frame_read_count,capture_fps,inference_count,"
        "inference_fps,last_gap_s,max_gap_s,status\n"
    )

    try:
        while True:
            now = time.perf_counter()
            if now >= deadline:
                break

            ok, frame_bgr = cap.read()
            if not ok or frame_bgr is None:
                print("WARN: failed to read frame from camera")
                continue
            frame_read_count += 1

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(frame_rgb, (int(input_w), int(input_h)))
            input_tensor = np.expand_dims(resized, axis=0).astype(input_dtype)

            interpreter.set_tensor(input_details[0]["index"], input_tensor)
            interpreter.invoke()

            inference_time = time.perf_counter()
            inference_count += 1

            gap_seconds = inference_time - prev_inference_time
            prev_inference_time = inference_time
            max_observed_gap_seconds = max(max_observed_gap_seconds, gap_seconds)
            elapsed = inference_time - start_time

            while (
                next_snapshot_time is not None
                and snapshot_index < SNAPSHOT_COUNT
                and inference_time >= next_snapshot_time
            ):
                snapshot_index += 1
                write_metrics_snapshot(
                    log_handle=log_handle,
                    snapshot_number=snapshot_index,
                    elapsed=elapsed,
                    frame_read_count=frame_read_count,
                    inference_count=inference_count,
                    last_gap_seconds=gap_seconds,
                    max_gap_seconds=max_observed_gap_seconds,
                    status="ok",
                )
                next_snapshot_time += snapshot_interval_seconds

            if gap_seconds > args.max_gap_seconds:
                stall_detected = True
                print(
                    f"FAIL: detected loop gap of {gap_seconds:.2f}s "
                    f"(allowed {args.max_gap_seconds:.2f}s)"
                )
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                capture_fps = frame_read_count / elapsed if elapsed > 0 else 0.0
                inference_fps = inference_count / elapsed if elapsed > 0 else 0.0
                log_handle.write(
                    f"{timestamp},stall_fail,{elapsed:.3f},{frame_read_count},{capture_fps:.3f},"
                    f"{inference_count},{inference_fps:.3f},{gap_seconds:.3f},"
                    f"{max_observed_gap_seconds:.3f},fail\n"
                )
                log_handle.flush()
                break

            if args.show_window:
                capture_fps_live = frame_read_count / elapsed if elapsed > 0 else 0.0
                inference_fps_live = inference_count / elapsed if elapsed > 0 else 0.0

                cv2.putText(
                    frame_bgr,
                    f"inference #{inference_count} infer_fps={inference_fps_live:.2f} cap_fps={capture_fps_live:.2f}",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
                cv2.imshow("TP-12 Detection Loop Test", frame_bgr)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("FAIL: quit early with 'q' before reaching duration.")
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    capture_fps = frame_read_count / elapsed if elapsed > 0 else 0.0
                    inference_fps = inference_count / elapsed if elapsed > 0 else 0.0
                    log_handle.write(
                        f"{timestamp},manual_quit_fail,{elapsed:.3f},{frame_read_count},{capture_fps:.3f},"
                        f"{inference_count},{inference_fps:.3f},{gap_seconds:.3f},"
                        f"{max_observed_gap_seconds:.3f},fail\n"
                    )
                    log_handle.flush()
                    return 1
    finally:
        cap.release()
        if args.show_window:
            cv2.destroyAllWindows()
        log_handle.close()

    elapsed_total = time.perf_counter() - start_time
    inference_fps = inference_count / elapsed_total if elapsed_total > 0 else 0.0
    capture_fps = frame_read_count / elapsed_total if elapsed_total > 0 else 0.0

    print(
        f"Run complete: elapsed={elapsed_total:.2f}s frames={frame_read_count} "
        f"capture_fps={capture_fps:.2f} inferences={inference_count} infer_fps={inference_fps:.2f}"
    )

    if stall_detected:
        print("TP-12 FAILED: loop stall detected.")
        return 1

    if elapsed_total + 0.05 < args.duration_seconds:
        print("TP-12 FAILED: loop did not run for full requested duration.")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with metrics_log_file.open("a", encoding="utf-8") as log_append:
            log_append.write(
                f"{timestamp},duration_fail,{elapsed_total:.3f},{frame_read_count},{capture_fps:.3f},"
                f"{inference_count},{inference_fps:.3f},0.000,{max_observed_gap_seconds:.3f},fail\n"
            )
        return 1

    if inference_count <= 0:
        print("TP-12 FAILED: no inferences executed.")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with metrics_log_file.open("a", encoding="utf-8") as log_append:
            log_append.write(
                f"{timestamp},no_inference_fail,{elapsed_total:.3f},{frame_read_count},{capture_fps:.3f},"
                f"{inference_count},{inference_fps:.3f},0.000,{max_observed_gap_seconds:.3f},fail\n"
            )
        return 1

    print("TP-12 PASSED: continuous inference loop completed without stall/crash.")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with metrics_log_file.open("a", encoding="utf-8") as log_append:
        log_append.write(
            f"{timestamp},pass,{elapsed_total:.3f},{frame_read_count},{capture_fps:.3f},"
            f"{inference_count},{inference_fps:.3f},0.000,{max_observed_gap_seconds:.3f},pass\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())