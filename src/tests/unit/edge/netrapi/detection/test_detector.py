from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from config.types import DetectorConfig
from netrapi.buffer import Classification
from netrapi.detection import Detector
from netrapi.exceptions import DetectionError

EDGE_DIR = Path(__file__).resolve().parents[5] / "main" / "edge"


def _detector_config(tmp_path: Path, *, input_dtype: str = "uint8") -> DetectorConfig:
    labels = tmp_path / "labels.txt"
    labels.write_text("stop sign\nperson\n", encoding="utf-8")
    return DetectorConfig(
        model_path=EDGE_DIR / "models" / "ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite",
        labels_path=labels,
        input_width=320,
        input_height=320,
        channels=3,
        input_dtype=input_dtype,
        score_threshold=0.5,
        top_k=2,
        allowed_classes={"stop sign"},
    )


def test_classify_returns_filtered_detections(tmp_path: Path):
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    detector = Detector(_detector_config(tmp_path))
    mock_detections = [
        Classification("stop sign", 0.91, (0.1, 0.2, 0.3, 0.4)),
        Classification("person", 0.99, (0.0, 0.0, 1.0, 1.0)),
    ]

    with (
        patch.object(detector, "_preprocess", return_value=np.zeros((1, 1, 3), dtype=np.uint8)),
        patch.object(detector, "_invoke", return_value=mock_detections),
    ):
        results = detector.classify(frame)

    assert len(results) == 1
    assert results[0].label == "stop sign"
    assert results[0].score == pytest.approx(0.91)


def test_preprocess_resizes_and_adds_batch_dimension(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    rgb = np.ones((48, 64, 3), dtype=np.uint8)
    resized = np.full((320, 320, 3), 128, dtype=np.uint8)

    mock_cv2 = MagicMock()
    mock_cv2.cvtColor.return_value = rgb
    mock_cv2.resize.return_value = resized
    mock_cv2.COLOR_BGR2RGB = 4

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        result = detector._preprocess(frame)

    mock_cv2.cvtColor.assert_called_once_with(frame, mock_cv2.COLOR_BGR2RGB)
    mock_cv2.resize.assert_called_once_with(rgb, (320, 320))
    assert result.shape == (1, 320, 320, 3)
    assert result.dtype == np.uint8
    assert result[0, 0, 0, 0] == 128


def test_preprocess_rejects_non_3d_array(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))

    with pytest.raises(DetectionError, match="3-D array"):
        detector._preprocess(np.zeros((48, 64), dtype=np.uint8))


def test_normalize_resized_uint8(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))
    resized = np.full((10, 10, 3), 200, dtype=np.uint8)

    result = detector._normalize_resized(resized)

    assert result.dtype == np.uint8
    assert result[0, 0, 0] == 200


def test_normalize_resized_float32(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path, input_dtype="float32"))
    resized = np.full((10, 10, 3), 255, dtype=np.uint8)

    result = detector._normalize_resized(resized)

    assert result.dtype == np.float32
    assert result[0, 0, 0] == pytest.approx(1.0)


def test_invoke_raises_when_model_not_loaded(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))

    with pytest.raises(DetectionError, match="not loaded"):
        detector._invoke(np.zeros((1, 320, 320, 3), dtype=np.uint8))


def test_invoke_runs_interpreter_and_parses_output(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))
    detector._labels = {0: "stop sign"}

    boxes = np.array([[0.1, 0.2, 0.3, 0.4]], dtype=np.float32)
    classes = np.array([0.0], dtype=np.float32)
    scores = np.array([0.91], dtype=np.float32)
    count = np.array([1], dtype=np.float32)

    interpreter = MagicMock()
    interpreter.get_input_details.return_value = [{"index": 0}]
    interpreter.get_output_details.return_value = [
        {"index": 0},
        {"index": 1},
        {"index": 2},
        {"index": 3},
    ]
    interpreter.get_tensor.side_effect = lambda index: {
        0: np.expand_dims(boxes, axis=0),
        1: np.expand_dims(classes, axis=0),
        2: np.expand_dims(scores, axis=0),
        3: count,
    }[index]
    detector._inference_model = interpreter

    model_input = np.zeros((1, 320, 320, 3), dtype=np.uint8)
    results = detector._invoke(model_input)

    interpreter.set_tensor.assert_called_once_with(0, model_input)
    interpreter.invoke.assert_called_once()
    assert len(results) == 1
    assert results[0].label == "stop sign"
    assert results[0].score == pytest.approx(0.91)
    assert results[0].box == pytest.approx((0.1, 0.2, 0.3, 0.4))


def test_parse_model_output_maps_labels_and_boxes(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))
    detector._labels = {0: "stop sign", 1: "person"}

    boxes = np.array(
        [
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8],
        ],
        dtype=np.float32,
    )
    classes = np.array([0.0, 1.0], dtype=np.float32)
    scores = np.array([0.91, 0.75], dtype=np.float32)

    results = detector._parse_model_output(boxes, classes, scores, count=2)

    assert len(results) == 2
    assert results[0].label == "stop sign"
    assert results[0].score == pytest.approx(0.91)
    assert results[0].box == pytest.approx((0.1, 0.2, 0.3, 0.4))
    assert results[1].label == "person"
    assert results[1].score == pytest.approx(0.75)
    assert results[1].box == pytest.approx((0.5, 0.6, 0.7, 0.8))


def test_parse_model_output_uses_fallback_label_for_unknown_class(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))
    detector._labels = {0: "stop sign"}

    results = detector._parse_model_output(
        np.array([[0.0, 0.0, 1.0, 1.0]], dtype=np.float32),
        np.array([99.0], dtype=np.float32),
        np.array([0.8], dtype=np.float32),
        count=1,
    )

    assert results[0].label == "class_99"


def test_parse_model_output_respects_count_limit(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))
    detector._labels = {0: "stop sign"}

    results = detector._parse_model_output(
        np.array([[0.0, 0.0, 1.0, 1.0], [0.1, 0.2, 0.3, 0.4]], dtype=np.float32),
        np.array([0.0, 0.0], dtype=np.float32),
        np.array([0.9, 0.8], dtype=np.float32),
        count=1,
    )

    assert len(results) == 1
    assert results[0].score == pytest.approx(0.9)


def test_filter_applies_threshold_top_k_and_allow_list(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))
    raw = [
        Classification("stop sign", 0.4, (0, 0, 1, 1)),
        Classification("stop sign", 0.95, (0, 0, 1, 1)),
        Classification("stop sign", 0.85, (0, 0, 1, 1)),
        Classification("person", 0.99, (0, 0, 1, 1)),
    ]
    results = detector._filter_detections(raw)

    assert len(results) == 2
    assert results[0].score == pytest.approx(0.95)
    assert results[1].score == pytest.approx(0.85)
    assert all(item.label == "stop sign" for item in results)


def test_dummy_input_uint8(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))

    dummy = detector._dummy_input()

    assert dummy.shape == (1, 320, 320, 3)
    assert dummy.dtype == np.uint8
    assert dummy.sum() == 0


def test_dummy_input_float32(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path, input_dtype="float32"))

    dummy = detector._dummy_input()

    assert dummy.shape == (1, 320, 320, 3)
    assert dummy.dtype == np.float32
    assert dummy.sum() == pytest.approx(0.0)


def test_verify_tpu_requires_load(tmp_path: Path):
    detector = Detector(_detector_config(tmp_path))

    with pytest.raises(DetectionError, match="not loaded"):
        detector.verify_tpu()
