"""Prepare AT-3.4 frozen config, local training data copy, and sklearn kNN joblib artifacts.

Hardcoded to ap_050 (window_5_motion_area_2_stopped_lo_k3_min_area). No experiment CLI.

Usage (from repo root):

    python src/tests/integration/at_3_4/prepare_at_3_4_config.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
BATCH_LIB = REPO_ROOT / "src/tests/analysis/batch_analysis/scripts/lib"
CONFIG_DIR = SCRIPT_DIR / "config"
DATA_DIR = SCRIPT_DIR / "data"
SOURCE_DATA_DIR = (
    REPO_ROOT / "src/tests/analysis/batch_analysis/evaluation/motion_area_2/data"
)
EXCEL_PATH = REPO_ROOT / "src/tests/analysis/live_motion_analysis/ex_motion.xlsx"
COPY_MANIFEST = DATA_DIR / ".copy_manifest.json"

APPROACH_CONFIG = {
    "min_peak_pct": 0.25,
    "min_approach_s": 0.35,
    "max_approach_s": 12.0,
    "approach_start_peak_ratio": 0.10,
    "min_increasing_fraction": 0.50,
    "min_log_linear_r2": 0.30,
    "drop_within_s": 2.5,
    "drop_to_peak_ratio": 0.12,
    "post_drop_peak_ratio": 2.5,
    "post_drop_hold_s": 0.05,
}

MOTION_CONFIG = {
    "motion_roi": {"x_min": 0.25, "x_max": 0.75, "y_min": 0.55, "y_max": 0.95},
    "flow_scale": 0.5,
    "motion_smoothing_window": 5,
    "stopped_motion_threshold": 0.6,
    "crawl_motion_threshold": 2.5,
    "farneback": {
        "pyr_scale": 0.5,
        "levels": 3,
        "winsize": 15,
        "iterations": 3,
        "poly_n": 5,
        "poly_sigma": 1.2,
    },
}

METRICS_CONFIG = {"post_drop_window_s": 5.0}

DETECTOR_CONFIG = {
    "score_threshold": 0.35,
    "min_box_center_x": 0.5,
}

KNN_CONFIG = {
    "k_neighbors": 3,
    "stage1_feature_names": [
        "post_drop_mean_motion",
        "post_drop_min_motion",
        "post_drop_p95_motion",
        "post_drop_stop_fraction",
    ],
    "stage2_feature_names": [
        "post_drop_min_motion",
        "approach_area_sum_pct",
    ],
}

PROVENANCE = {
    "experiment_id": "ap_050",
    "experiment_name": "window_5_motion_area_2_stopped_lo_k3_min_area",
    "reference_run_id": "20260705T174249Z",
    "reference_run_at": "2026-07-05T17:42:51Z",
    "offline_stage1_accuracy": "84.0%",
    "offline_e2e_accuracy": "83.3%",
    "offline_clip_count": 104,
    "excel_workbook": "src/tests/analysis/live_motion_analysis/ex_motion.xlsx",
    "source_data_copy": "src/tests/analysis/batch_analysis/evaluation/motion_area_2/data",
    "approach_source_row": "winner_pf02 on approach_config sheet",
    "motion_source_row": "stopped_lo on motion_config sheet (live stopped_motion_threshold=0.6)",
    "metrics_source_row": "window_5 on metrics_config sheet",
    "knn1_source_row": "k3 + runtime4 on knn1_config / feature_sets sheets",
    "knn2_source_row": "k3_min_area + min_area on knn2_config / feature_sets sheets",
    "approach_anchor": "per_frame_first_detect",
}


def _bootstrap() -> None:
    lib_str = str(BATCH_LIB)
    if lib_str not in sys.path:
        sys.path.insert(0, lib_str)
    pipeline_str = str(SCRIPT_DIR)
    if pipeline_str not in sys.path:
        sys.path.insert(0, pipeline_str)


def _source_fingerprint() -> str:
    if not SOURCE_DATA_DIR.is_dir():
        raise FileNotFoundError(f"Missing source data dir: {SOURCE_DATA_DIR}")
    areas = sorted(SOURCE_DATA_DIR.glob("*.areas.json"))
    motion = sorted(SOURCE_DATA_DIR.glob("*.motion.json"))
    digest = hashlib.sha256()
    digest.update(f"areas={len(areas)}:motion={len(motion)}".encode())
    for path in areas[:3]:
        digest.update(path.name.encode())
    return digest.hexdigest()[:16]


def _copy_training_data() -> tuple[int, int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fingerprint = _source_fingerprint()
    if COPY_MANIFEST.is_file():
        try:
            manifest = json.loads(COPY_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
        if manifest.get("fingerprint") == fingerprint:
            return int(manifest.get("areas_count", 0)), int(manifest.get("motion_count", 0))

    areas_count = 0
    motion_count = 0
    for pattern in ("*.areas.json", "*.motion.json"):
        for source in sorted(SOURCE_DATA_DIR.glob(pattern)):
            target = DATA_DIR / source.name
            shutil.copy2(source, target)
            if pattern.startswith("*.areas"):
                areas_count += 1
            else:
                motion_count += 1

    COPY_MANIFEST.write_text(
        json.dumps(
            {
                "fingerprint": fingerprint,
                "copied_at": datetime.now(timezone.utc).isoformat(),
                "areas_count": areas_count,
                "motion_count": motion_count,
                "source": str(SOURCE_DATA_DIR.relative_to(REPO_ROOT)).replace("\\", "/"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return areas_count, motion_count


def _write_json_configs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "approach_config.json").write_text(
        json.dumps(APPROACH_CONFIG, indent=2), encoding="utf-8"
    )
    (CONFIG_DIR / "motion_config.json").write_text(
        json.dumps(MOTION_CONFIG, indent=2), encoding="utf-8"
    )
    (CONFIG_DIR / "metrics_config.json").write_text(
        json.dumps(METRICS_CONFIG, indent=2), encoding="utf-8"
    )
    (CONFIG_DIR / "detector_config.json").write_text(
        json.dumps(DETECTOR_CONFIG, indent=2), encoding="utf-8"
    )
    (CONFIG_DIR / "knn_config.json").write_text(
        json.dumps(KNN_CONFIG, indent=2), encoding="utf-8"
    )


def _fit_pipeline(items: list[tuple[str, list[float]]], k: int):
    try:
        import joblib
        import numpy as np
        from sklearn.impute import SimpleImputer
        from sklearn.neighbors import KNeighborsClassifier
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise SystemExit(
            "prepare_at_3_4_config requires scikit-learn and joblib: pip install scikit-learn joblib"
        ) from exc

    if not items:
        return None

    labels = [label for label, _features in items]
    if len(set(labels)) < 2:
        return None

    matrix = np.asarray([features for _label, features in items], dtype=float)
    if len(labels) < k + 1:
        k = max(1, len(labels) - 1)

    pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", KNeighborsClassifier(n_neighbors=k, weights="distance")),
        ]
    )
    pipeline.fit(matrix, labels)
    return pipeline, joblib


def _train_knn() -> dict[str, object]:
    from area_series_cache import load_areas_from_processed_file
    from clip_labels import clip_id_from_name, single_tagged_clips
    from knn_feature_registry import build_clip_feature_context, extract_knn_features
    from motion_score_series import motion_config_from_dict
    from motion_series_cache import load_motion_from_processed_file
    from per_frame_approach_sim import PerFrameConfig, detect_approach_per_frame
    from stop_behavior_classifier import (
        is_stop_behavior_label,
        to_binary_stop_label,
        to_unsafe_subtype_label,
    )
    from stop_sign_approach_pattern import ApproachDropConfig

    from at_3_4_pipeline import STAGE1_FEATURE_NAMES, STAGE2_FEATURE_NAMES

    approach_config = ApproachDropConfig(**APPROACH_CONFIG)
    motion_config = motion_config_from_dict(MOTION_CONFIG)
    post_drop_window_s = float(METRICS_CONFIG["post_drop_window_s"])
    k = int(KNN_CONFIG["k_neighbors"])
    per_frame_config = PerFrameConfig(post_drop_window_s=post_drop_window_s)

    labels_by_id = {clip_id: label for clip_id, _tag, label in single_tagged_clips()}

    stage1_items: list[tuple[str, list[float]]] = []
    stage2_items: list[tuple[str, list[float]]] = []

    for areas_file in sorted(DATA_DIR.glob("*.areas.json")):
        clip_id = clip_id_from_name(areas_file.name)
        if clip_id is None:
            continue
        label = labels_by_id.get(clip_id)
        if not label or not is_stop_behavior_label(label):
            continue

        motion_file = DATA_DIR / f"{areas_file.stem.removesuffix('.areas')}.motion.json"
        if not motion_file.is_file():
            continue

        loaded_areas = load_areas_from_processed_file(areas_file)
        loaded_motion = load_motion_from_processed_file(motion_file)
        if loaded_areas is None or loaded_motion is None:
            continue

        areas, fps, _name = loaded_areas
        motion_scores, motion_fps, _motion_name = loaded_motion
        if motion_fps > 0:
            fps = motion_fps

        detect_frame, detect_time_s = detect_approach_per_frame(
            areas,
            fps,
            approach_config=approach_config,
            per_frame_config=per_frame_config,
        )
        if detect_time_s is None or detect_frame is None:
            continue

        ctx = build_clip_feature_context(
            areas=areas,
            motion_scores=motion_scores,
            fps=fps,
            detect_frame=detect_frame,
            detect_time_s=detect_time_s,
            approach_config=approach_config,
            window_s=post_drop_window_s,
            stopped_threshold=motion_config.stopped_motion_threshold,
            crawl_threshold=motion_config.crawl_motion_threshold,
        )
        if ctx is None:
            continue

        stage1_features = extract_knn_features(ctx, STAGE1_FEATURE_NAMES)
        stage2_features = extract_knn_features(ctx, STAGE2_FEATURE_NAMES)
        if stage1_features is None or stage2_features is None:
            continue

        binary_label = to_binary_stop_label(label)
        if binary_label is not None:
            stage1_items.append((binary_label, stage1_features))
        subtype_label = to_unsafe_subtype_label(label)
        if subtype_label is not None:
            stage2_items.append((subtype_label, stage2_features))

    stage1_result = _fit_pipeline(stage1_items, k)
    stage2_result = _fit_pipeline(stage2_items, k)
    if stage1_result is None:
        raise RuntimeError("Insufficient stage-1 training data after feature extraction.")
    if stage2_result is None:
        raise RuntimeError("Insufficient stage-2 training data after feature extraction.")

    stage1_pipeline, joblib = stage1_result
    joblib.dump(stage1_pipeline, CONFIG_DIR / "knn_stage1.joblib")

    stage2_pipeline, joblib = stage2_result
    joblib.dump(stage2_pipeline, CONFIG_DIR / "knn_stage2.joblib")

    return {
        "stage1_feature_names": list(STAGE1_FEATURE_NAMES),
        "stage2_feature_names": list(STAGE2_FEATURE_NAMES),
        "stage1_train_count": len(stage1_items),
        "stage2_train_count": len(stage2_items),
        "k_neighbors": k,
        "post_drop_window_s": post_drop_window_s,
        "stopped_motion_threshold": motion_config.stopped_motion_threshold,
    }


def main() -> int:
    _bootstrap()
    if not SOURCE_DATA_DIR.is_dir():
        print(f"Source data not found: {SOURCE_DATA_DIR}", file=sys.stderr)
        return 1

    areas_count, motion_count = _copy_training_data()
    print(f"Training data: {areas_count} areas + {motion_count} motion files in {DATA_DIR}")

    _write_json_configs()
    train_info = _train_knn()

    provenance = {
        **PROVENANCE,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "training_areas_files": areas_count,
        "training_motion_files": motion_count,
        **train_info,
    }
    (CONFIG_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

    print(f"Wrote configs and kNN joblib to {CONFIG_DIR}")
    print(
        f"  stage1_train_count={train_info['stage1_train_count']} "
        f"stage2_train_count={train_info['stage2_train_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
