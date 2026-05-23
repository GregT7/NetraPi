from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from config.types import DetectorConfig

from netrapi.buffer import Classification
from netrapi.exceptions import DetectionError


def _load_labels(label_path: Path) -> dict[int, str]:
    labels: dict[int, str] = {}
    text = label_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        parts = line.split(maxsplit=1)
        if len(parts) == 2 and parts[0].isdigit():
            labels[int(parts[0])] = parts[1]
        else:
            labels[index] = line

    return labels


class Detector:
    def __init__(self, config: DetectorConfig) -> None:
        self._config = config
        self._inference_model: Any | None = None
        self._labels: dict[int, str] = {}

    @property
    def config(self) -> DetectorConfig:
        return self._config

    def load(self) -> None:
        if not self._labels:
            if not self._config.labels_path.is_file():
                raise DetectionError(f"labels file not found: {self._config.labels_path}")
            self._labels = _load_labels(self._config.labels_path)

        if self._inference_model is not None:
            return

        if not self._config.model_path.is_file():
            raise DetectionError(f"model file not found: {self._config.model_path}")

        try:
            import tflite_runtime.interpreter as tflite
        except ImportError as exc:
            raise DetectionError("tflite_runtime is not installed") from exc

        delegates: list[Any] = []
        try:
            delegates = [tflite.load_delegate("libedgetpu.so.1")]
        except Exception:
            delegates = []

        interpreter = tflite.Interpreter(
            model_path=str(self._config.model_path),
            experimental_delegates=delegates,
        )
        interpreter.allocate_tensors()
        self._inference_model = interpreter

    def verify_tpu(self) -> bool:
        if self._inference_model is None:
            raise DetectionError("detector model is not loaded; call load() first")

        try:
            self._invoke(self._dummy_input())
            return True
        except Exception:
            return False

    def classify(self, raw: np.ndarray) -> list[Classification]:
        model_input = self._preprocess(raw)
        detections = self._invoke(model_input)
        return self._filter_detections(detections)

    def _preprocess(self, raw: np.ndarray) -> np.ndarray:
        import cv2

        image = np.asarray(raw)
        if image.ndim != 3:
            raise DetectionError("raw frame must be a 3-D array")

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(
            image_rgb,
            (self._config.input_width, self._config.input_height),
        )
        tensor = self._normalize_resized(resized)
        return np.expand_dims(tensor, axis=0)

    def _normalize_resized(self, resized: np.ndarray) -> np.ndarray:
        if self._config.input_dtype == "uint8":
            return resized.astype(np.uint8)
        return resized.astype(np.float32) / 255.0

    def _invoke(self, model_input: np.ndarray) -> list[Classification]:
        if self._inference_model is None:
            raise DetectionError("detector model is not loaded")

        interpreter = self._inference_model
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        interpreter.set_tensor(input_details[0]["index"], model_input)
        interpreter.invoke()

        boxes = interpreter.get_tensor(output_details[0]["index"])[0]
        classes = interpreter.get_tensor(output_details[1]["index"])[0]
        scores = interpreter.get_tensor(output_details[2]["index"])[0]
        count = int(interpreter.get_tensor(output_details[3]["index"])[0])

        return self._parse_model_output(boxes, classes, scores, count)

    def _parse_model_output(
        self,
        boxes: np.ndarray,
        classes: np.ndarray,
        scores: np.ndarray,
        count: int,
    ) -> list[Classification]:
        detections: list[Classification] = []
        limit = min(count, len(scores))

        for index in range(limit):
            score = float(scores[index])
            class_id = int(classes[index])
            label = self._labels.get(class_id, f"class_{class_id}")
            ymin, xmin, ymax, xmax = boxes[index]
            detections.append(
                Classification(
                    label=label,
                    score=score,
                    box=(float(ymin), float(xmin), float(ymax), float(xmax)),
                )
            )

        return detections

    def _filter_detections(self, detections: list[Classification]) -> list[Classification]:
        filtered: list[Classification] = []
        for detection in detections:
            if detection.score < self._config.score_threshold:
                continue
            if detection.label not in self._config.allowed_classes:
                continue
            filtered.append(detection)

        filtered.sort(key=lambda item: item.score, reverse=True)
        return filtered[: self._config.top_k]

    def _dummy_input(self) -> np.ndarray:
        shape = (1, self._config.input_height, self._config.input_width, 3)
        if self._config.input_dtype == "uint8":
            return np.zeros(shape, dtype=np.uint8)
        return np.zeros(shape, dtype=np.float32)
