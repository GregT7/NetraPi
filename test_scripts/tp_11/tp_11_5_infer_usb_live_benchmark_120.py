import os
import time
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite

CAMERA_INDEX = 0

MODEL_PATH = "/home/terrelgat/Desktop/diyTest/models/ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite"
LABEL_PATH = "/home/terrelgat/Desktop/diyTest/models/coco_labels.txt"

THRESHOLD = 0.5
TOP_K = 5

ALLOWED_CLASSES = {
    "stop sign",
    "person",
    "car",
    "truck",
    "bus",
    "bicycle",
    "motorcycle",
    "traffic light",
}

SAVE_EVERY_N_FRAMES = 30
ANNOTATED_DIR = "annotated_frames_usb"
SHOW_WINDOW = True

MAX_FRAMES = 120


def load_labels(path: str) -> Dict[int, str]:
    labels: Dict[int, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    for i, line in enumerate(lines):
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            labels[int(parts[0])] = parts[1]
        else:
            labels[i] = line
    return labels


def normalize_label(label: str) -> str:
    return label.strip().lower()


def clamp_box(x1: int, y1: int, x2: int, y2: int, width: int, height: int):
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(0, min(x2, width - 1))
    y2 = max(0, min(y2, height - 1))
    return x1, y1, x2, y2


def avg_ms(values: List[float]) -> float:
    return (sum(values) / len(values)) * 1000.0 if values else 0.0


def main() -> int:
    model_file = Path(MODEL_PATH)
    label_file = Path(LABEL_PATH)

    if not model_file.exists():
        raise FileNotFoundError(f"Model not found: {model_file}")
    if not label_file.exists():
        raise FileNotFoundError(f"Label file not found: {label_file}")

    os.makedirs(ANNOTATED_DIR, exist_ok=True)

    print("Loading labels...")
    labels = load_labels(str(label_file))

    print("Loading interpreter...")
    interpreter = tflite.Interpreter(
        model_path=str(model_file),
        experimental_delegates=[tflite.load_delegate("libedgetpu.so.1")],
    )
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    _, input_h, input_w, input_c = input_details[0]["shape"]
    input_dtype = input_details[0]["dtype"]

    print("Model ready")
    print("Input shape:", input_details[0]["shape"])
    print("Input dtype:", input_dtype)

    if input_c != 3:
        raise ValueError(f"Expected 3 input channels, got {input_c}")

    print(f"Opening USB camera at index {CAMERA_INDEX}...")
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open USB camera at index {CAMERA_INDEX}")

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    frame_idx = 0
    benchmark_start = time.perf_counter()

    acquisition_times: List[float] = []
    preprocess_times: List[float] = []
    inference_times: List[float] = []
    postprocess_times: List[float] = []
    total_loop_times: List[float] = []

    total_detections = 0
    frames_with_relevant_detections = 0

    try:
        while frame_idx < MAX_FRAMES:
            loop_start = time.perf_counter()

            t0 = time.perf_counter()
            ok, frame_bgr = cap.read()
            t1 = time.perf_counter()
            acquisition_times.append(t1 - t0)

            if not ok or frame_bgr is None:
                print("Failed to read frame from USB camera")
                continue

            t2 = time.perf_counter()
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(frame_rgb, (int(input_w), int(input_h)))
            input_tensor = np.expand_dims(resized, axis=0).astype(input_dtype)
            t3 = time.perf_counter()
            preprocess_times.append(t3 - t2)

            t4 = time.perf_counter()
            interpreter.set_tensor(input_details[0]["index"], input_tensor)
            interpreter.invoke()
            boxes = interpreter.get_tensor(output_details[0]["index"])[0]
            classes = interpreter.get_tensor(output_details[1]["index"])[0]
            scores = interpreter.get_tensor(output_details[2]["index"])[0]
            count = int(interpreter.get_tensor(output_details[3]["index"])[0])
            t5 = time.perf_counter()
            inference_times.append(t5 - t4)

            frame_idx += 1
            printed = 0
            kept_detections = 0

            annotated_frame = frame_bgr.copy()
            frame_h, frame_w = annotated_frame.shape[:2]

            t6 = time.perf_counter()
            for i in range(min(count, len(scores))):
                score = float(scores[i])
                if score < THRESHOLD:
                    continue

                class_id = int(classes[i])
                raw_label = labels.get(class_id, f"class_{class_id}")
                normalized = normalize_label(raw_label)

                if normalized not in ALLOWED_CLASSES:
                    continue

                ymin, xmin, ymax, xmax = boxes[i]

                x1 = int(xmin * frame_w)
                y1 = int(ymin * frame_h)
                x2 = int(xmax * frame_w)
                y2 = int(ymax * frame_h)

                x1, y1, x2, y2 = clamp_box(x1, y1, x2, y2, frame_w, frame_h)

                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    annotated_frame,
                    f"{raw_label} {score:.2f}",
                    (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

                print(
                    f"frame={frame_idx} "
                    f"label={raw_label} "
                    f"score={score:.3f} "
                    f"box=({y1}, {x1}, {y2}, {x2})"
                )

                printed += 1
                kept_detections += 1
                total_detections += 1

                if printed >= TOP_K:
                    break

            if kept_detections > 0:
                frames_with_relevant_detections += 1
            else:
                print(f"frame={frame_idx} no relevant detections above {THRESHOLD:.2f}")


            t7 = time.perf_counter()
            postprocess_times.append(t7 - t6)

            elapsed_total = t7 - benchmark_start
            fps = frame_idx / elapsed_total if elapsed_total > 0 else 0.0
            loop_ms_live = (t7 - loop_start) * 1000.0

            cv2.putText(
                annotated_frame,
                f"FPS: {fps:.2f}  loop_ms: {loop_ms_live:.1f}",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            if SHOW_WINDOW:
                cv2.imshow("USB Live Inference Benchmark", annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("Quitting early on 'q'")
                    break

            loop_end = time.perf_counter()
            total_loop_times.append(loop_end - loop_start)

        benchmark_end = time.perf_counter()

    finally:
        cap.release()
        if SHOW_WINDOW:
            cv2.destroyAllWindows()

    processed_frames = len(total_loop_times)
    total_elapsed = benchmark_end - benchmark_start if processed_frames > 0 else 0.0
    effective_fps = processed_frames / total_elapsed if total_elapsed > 0 else 0.0

    avg_total_loop_ms = avg_ms(total_loop_times)
    avg_acquisition_ms = avg_ms(acquisition_times[:processed_frames])
    avg_preprocess_ms = avg_ms(preprocess_times[:processed_frames])
    avg_inference_ms = avg_ms(inference_times[:processed_frames])
    avg_postprocess_ms = avg_ms(postprocess_times[:processed_frames])

    stage_avgs = {
        "frame acquisition": avg_acquisition_ms,
        "preprocess": avg_preprocess_ms,
        "inference": avg_inference_ms,
        "postprocess/annotation": avg_postprocess_ms,
    }
    dominant_stage = max(stage_avgs, key=stage_avgs.get)

    print("\n" + "=" * 60)
    print("TP-11.5 BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"Processed frames: {processed_frames}")
    print(f"Elapsed time (s): {total_elapsed:.3f}")
    print(f"Effective processed FPS: {effective_fps:.3f}")
    print(f"Average total loop time (ms): {avg_total_loop_ms:.3f}")
    print(f"Average frame acquisition time (ms): {avg_acquisition_ms:.3f}")
    print(f"Average preprocess time (ms): {avg_preprocess_ms:.3f}")
    print(f"Average inference time (ms): {avg_inference_ms:.3f}")
    print(f"Average postprocess/annotation time (ms): {avg_postprocess_ms:.3f}")
    print(f"Frames with relevant detections: {frames_with_relevant_detections}")
    print(f"Total relevant detections printed: {total_detections}")
    print(f"Dominant contributor to loop time: {dominant_stage} ({stage_avgs[dominant_stage]:.3f} ms)")
    print("=" * 60)

    if effective_fps >= 5.0:
        print("FPS result: PASS (preferred target met: >= 5 FPS)")
    elif effective_fps >= 3.0:
        print("FPS result: PARTIAL PASS (minimum exploratory threshold met: >= 3 FPS)")
    else:
        print("FPS result: BELOW TARGET (< 3 FPS)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())