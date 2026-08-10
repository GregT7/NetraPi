import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite


def load_labels(label_path: str) -> Dict[int, str]:
    """
    Load labels from a text file.
    Supported formats:
    - one label per line
    - 'id label' per line
    """
    labels: Dict[int, str] = {}

    with open(label_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    for i, line in enumerate(lines):
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            labels[int(parts[0])] = parts[1]
        else:
            labels[i] = line

    return labels


def make_interpreter(model_path: str) -> tflite.Interpreter:
    interpreter = tflite.Interpreter(
        model_path=model_path,
        experimental_delegates=[tflite.load_delegate("libedgetpu.so.1")],
    )
    interpreter.allocate_tensors()
    return interpreter


def preprocess_image(
    image_bgr: np.ndarray,
    input_width: int,
    input_height: int,
    input_dtype: np.dtype,
) -> np.ndarray:
    """
    Convert BGR -> RGB, resize to model input, add batch dimension.
    """
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(image_rgb, (input_width, input_height))

    if input_dtype == np.uint8:
        input_tensor = resized.astype(np.uint8)
    elif input_dtype == np.float32:
        input_tensor = resized.astype(np.float32) / 255.0
    else:
        raise ValueError(f"Unsupported input dtype: {input_dtype}")

    return np.expand_dims(input_tensor, axis=0)


def run_inference(
    interpreter: tflite.Interpreter,
    input_tensor: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    interpreter.set_tensor(input_details[0]["index"], input_tensor)
    interpreter.invoke()

    boxes = interpreter.get_tensor(output_details[0]["index"])[0]
    classes = interpreter.get_tensor(output_details[1]["index"])[0]
    scores = interpreter.get_tensor(output_details[2]["index"])[0]
    count = int(interpreter.get_tensor(output_details[3]["index"])[0])

    return boxes, classes, scores, count


def clamp(val: int, low: int, high: int) -> int:
    return max(low, min(val, high))


def draw_detections(
    image_bgr: np.ndarray,
    boxes: np.ndarray,
    classes: np.ndarray,
    scores: np.ndarray,
    count: int,
    score_threshold: float,
    labels: Dict[int, str],
) -> np.ndarray:
    output = image_bgr.copy()
    h, w = output.shape[:2]

    for i in range(min(count, len(scores))):
        score = float(scores[i])
        if score < score_threshold:
            continue

        ymin, xmin, ymax, xmax = boxes[i]

        x1 = clamp(int(xmin * w), 0, w - 1)
        y1 = clamp(int(ymin * h), 0, h - 1)
        x2 = clamp(int(xmax * w), 0, w - 1)
        y2 = clamp(int(ymax * h), 0, h - 1)

        class_id = int(classes[i])
        label = labels.get(class_id, f"class_{class_id}")
        text = f"{label}: {score:.2f}"

        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)

        text_y = max(y1 - 10, 20)
        cv2.putText(
            output,
            text,
            (x1, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

    return output


def print_detections(
    boxes: np.ndarray,
    classes: np.ndarray,
    scores: np.ndarray,
    count: int,
    score_threshold: float,
    labels: Dict[int, str],
) -> None:
    print(f"Detection count reported by model: {count}")

    shown = 0
    for i in range(min(count, len(scores))):
        score = float(scores[i])
        if score < score_threshold:
            continue

        ymin, xmin, ymax, xmax = boxes[i]
        class_id = int(classes[i])
        label = labels.get(class_id, f"class_{class_id}")

        print(
            f"[{i}] label={label} class_id={class_id} score={score:.3f} "
            f"box=(ymin={ymin:.3f}, xmin={xmin:.3f}, ymax={ymax:.3f}, xmax={xmax:.3f})"
        )
        shown += 1

    if shown == 0:
        print(f"No detections above threshold {score_threshold:.2f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Edge TPU object detection on one image.")
    parser.add_argument("--model", required=True, help="Path to Edge TPU .tflite model")
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument(
        "--labels",
        default=None,
        help="Optional path to label file",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.30,
        help="Score threshold for printing/drawing detections",
    )
    parser.add_argument(
        "--output",
        default="annotated_output.jpg",
        help="Path to save annotated image",
    )
    args = parser.parse_args()

    model_path = Path(args.model)
    image_path = Path(args.image)
    output_path = Path(args.output)

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    labels: Dict[int, str] = {}
    if args.labels:
        label_path = Path(args.labels)
        if not label_path.exists():
            raise FileNotFoundError(f"Label file not found: {label_path}")
        labels = load_labels(str(label_path))

    print("Loading interpreter...")
    interpreter = make_interpreter(str(model_path))

    input_details = interpreter.get_input_details()
    input_shape = input_details[0]["shape"]
    input_dtype = input_details[0]["dtype"]

    _, input_height, input_width, input_channels = input_shape
    print(f"Model input shape: {input_shape}")
    print(f"Model input dtype: {input_dtype}")

    if input_channels != 3:
        raise ValueError(f"Expected 3-channel RGB input, got {input_channels}")

    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise ValueError(f"Failed to load image: {image_path}")

    input_tensor = preprocess_image(
        image_bgr=image_bgr,
        input_width=int(input_width),
        input_height=int(input_height),
        input_dtype=input_dtype,
    )

    boxes, classes, scores, count = run_inference(interpreter, input_tensor)

    print_detections(
        boxes=boxes,
        classes=classes,
        scores=scores,
        count=count,
        score_threshold=args.threshold,
        labels=labels,
    )

    annotated = draw_detections(
        image_bgr=image_bgr,
        boxes=boxes,
        classes=classes,
        scores=scores,
        count=count,
        score_threshold=args.threshold,
        labels=labels,
    )

    ok = cv2.imwrite(str(output_path), annotated)
    if not ok:
        raise RuntimeError(f"Failed to save annotated image: {output_path}")

    print(f"Annotated image saved to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())