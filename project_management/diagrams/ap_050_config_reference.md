# `ap_050` — full configuration reference

**Source workbook:** `live_motion_analysis/ex_motion.xlsx`  
**Last recorded run:** `20260705T174249Z` (2026-07-05 17:42:51Z)  
**Purpose:** Live motion kNN pipeline on **`motion_area_2`** batch cache — 5 s post-drop window, low stop threshold, k=3 stage-1 (4 motion features), k=3 stage-2 (min motion + approach area sum).

Use this document when porting **`ap_050`** values into edge code or integration tests.

---

## 1. Experiment identity

| Field | Value |
|-------|-------|
| `experiment_id` | `ap_050` |
| `experiment_name` | `window_5_motion_area_2_stopped_lo_k3_min_area` |
| `data_set` | `motion_area_2` |
| `approach_id` | `winner_pf02` |
| `motion_id` | `stopped_lo` |
| `metrics_id` | `window_5` |
| `knn1_id` | `k3` |
| `knn2_id` | `k3_min_area` |

**Batch data path:** `batch_analysis/evaluation/motion_area_2/data/`  
(`*.areas.json`, `*.motion.json` — motion scores computed at **batch** preprocess time)

**Workbook sheets involved:**

| Sheet | Role |
|-------|------|
| `experiments` | Profile ID pointers |
| `approach_config` | Live approach thresholds (`winner_pf02`) |
| `motion_config` | Live `stopped_motion_threshold` only (`stopped_lo`) |
| `metrics_config` | Live `post_drop_window_s` (`window_5`) |
| `knn1_config` / `knn2_config` | k and feature-set IDs |
| `feature_sets` | Boolean columns per feature name |
| `experiment_config` | Full flattened snapshot written on each run |

---

## 2. Pipeline overview

```
Per frame: detect stop sign → append area to prefix buffer
         → prefix approach detect (winner_pf02) → T₀
         → slice motion scores [T₀, T₀ + 5s] with stopped_threshold=0.6
         → Stage-1 kNN (k=3, 4 features) → complete-stop | rolling-or-run-through
         → if rolling-or-run-through: Stage-2 kNN (k=3, 2 features) → rolling-stop | run-through
         → e2e label from stage1 + stage2
```

**Stage-1 classes:** `complete-stop`, `rolling-or-run-through`  
**Stage-2 classes (unsafe only):** `rolling-stop`, `run-through`  
**e2e mapping:**

- `complete-stop` → e2e `complete-stop`
- `rolling-or-run-through` + stage2 → e2e = stage2 label (`rolling-stop` or `run-through`)

---

## 3. Live knobs (from Excel — use at runtime)

These override batch JSON for live sim / Pi. Values match the `experiment_config` snapshot row for `ap_050`.

### 3.1 Approach — `winner_pf02`

| Parameter | Value | Notes |
|-----------|-------|-------|
| `min_peak_pct` | **0.25** | Peak area ≥ 0.25% of frame |
| `min_approach_s` | **0.35** | Min approach duration (s) |
| `max_approach_s` | **12.0** | Max approach duration (s) |
| `approach_start_peak_ratio` | **0.10** | Walk-back threshold = 10% of peak |
| `min_increasing_fraction` | **0.50** | Rising steps fraction |
| `min_log_linear_r2` | **0.30** | Log-linear fit floor |
| `drop_within_s` | **2.5** | Drop must occur within 2.5 s of peak |
| `drop_to_peak_ratio` | **0.12** | Drop when area ≤ 12% of peak |
| `post_drop_peak_ratio` | **2.5** | Post-drop hold ratio |
| `post_drop_hold_s` | **0.05** | Hold 50 ms after drop |

```json
{
  "min_peak_pct": 0.25,
  "min_approach_s": 0.35,
  "max_approach_s": 12.0,
  "approach_start_peak_ratio": 0.1,
  "min_increasing_fraction": 0.5,
  "min_log_linear_r2": 0.3,
  "drop_within_s": 2.5,
  "drop_to_peak_ratio": 0.12,
  "post_drop_peak_ratio": 2.5,
  "post_drop_hold_s": 0.05
}
```

Matches edge `src/main/edge/config/approach_config.json` (no `gap_fill_max_s` / `envelope_window_s`). Those area-series smoothers exist only in some offline analysis configs/scripts and are **not** used on the Pi.

> **Note:** `batch_analysis/evaluation/motion_area_2/config/approach_config.json` on disk differs (e.g. `min_approach_s: 0.20`, smoothing on). **`ap_050` / edge use the values above**, not that batch file.

### 3.2 Motion (live) — `stopped_lo`

| Parameter | Value | Notes |
|-----------|-------|-------|
| `stopped_motion_threshold` | **0.6** | Frames with motion score ≤ 0.6 count as “stopped” for **`post_drop_stop_fraction`** and runtime kNN |

Only this field is a live knob. ROI, Farneback, and per-frame motion scores come from batch preprocess (§4.2).

### 3.3 Metrics (live) — `window_5`

| Parameter | Value | Notes |
|-----------|-------|-------|
| `post_drop_window_s` | **5.0** | Classification window length after T₀ |

### 3.4 Stage-1 kNN — `k3` + `feature_sets.runtime4`

| Parameter | Value |
|-----------|-------|
| `k_neighbors` | **3** |
| `feature_set_id` | **`runtime4`** |

**Enabled features (order matters for the vector):**

| # | Feature | Description |
|---|---------|-------------|
| 1 | `post_drop_mean_motion` | Mean motion in [T₀, T₀+5s] |
| 2 | `post_drop_min_motion` | Min motion in window |
| 3 | `post_drop_p95_motion` | 95th percentile motion in window |
| 4 | `post_drop_stop_fraction` | Fraction of window frames with score ≤ **0.6** |

**Stage-1 feature vector:** `[mean, min, p95, stop_fraction]` (4 dimensions)

### 3.5 Stage-2 kNN — `k3_min_area` + `feature_sets.min_area`

| Parameter | Value |
|-----------|-------|
| `k_neighbors` | **3** |
| `feature_set_id` | **`min_area`** |

**Enabled features:**

| # | Feature | Description |
|---|---------|-------------|
| 1 | `post_drop_min_motion` | Min motion in [T₀, T₀+5s] |
| 2 | `approach_area_sum_pct` | Sum of sign area% from approach start through drop end (prefix event) |

**Stage-2 feature vector:** `[post_drop_min_motion, approach_area_sum_pct]` (2 dimensions)

`approach_area_sum_pct` is computed from the **same prefix** used for T₀ (not whole-clip offline timing). See `batch_analysis/scripts/lib/knn_feature_registry.py`.

---

## 4. Batch / preprocess (frozen in `motion_area_2`)

From `batch_analysis/evaluation/motion_area_2/config/` and the `experiment_config` snapshot. Used for cached `*.areas.json` / `*.motion.json` and offline detection graphs — **not** for live approach thresholds.

### 4.1 Detector — `detector_config.json`

| Parameter | Value |
|-----------|-------|
| `model_path` | `src/tests/analysis/batch_analysis/models/ssdlite_mobiledet_coco_qat_postprocess.tflite` |
| `labels_path` | `src/main/edge/models/coco_labels.txt` |
| `input_width` / `input_height` | **320** / **320** |
| `input_dtype` | `uint8` |
| `score_threshold` | **0.35** |
| `top_k` | **5** |
| `allowed_classes` | `["stop sign"]` |
| `min_box_center_x` | **0.5** (ignore signs left of midline) |

**Pi production model (AT-3.4):** Edge TPU variant at `src/main/edge/models/ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite` — same architecture/thresholds, different runtime.

### 4.2 Motion preprocess — `motion_config.json` (batch)

Used when building `*.motion.json` (Farneback on ROI). **Not** the live `stopped_motion_threshold` (0.6).

| Parameter | Value |
|-----------|-------|
| `motion_roi.x_min` / `x_max` | **0.25** / **0.75** |
| `motion_roi.y_min` / `y_max` | **0.55** / **0.95** |
| `flow_scale` | **0.5** |
| `motion_smoothing_window` | **5** |
| `stopped_motion_threshold` (batch) | **0.8** |
| `crawl_motion_threshold` | **2.5** |
| `farneback.pyr_scale` | **0.5** |
| `farneback.levels` | **3** |
| `farneback.winsize` | **15** |
| `farneback.iterations` | **3** |
| `farneback.poly_n` | **5** |
| `farneback.poly_sigma` | **1.2** |

### 4.3 Batch metrics JSON (exploration only)

`motion_area_2/config/metrics_config.json` has `post_drop_window_s: 10.0` — used for `metrics_exploration.csv` only, **not** for `ap_050` live window (5 s from Excel).

---

## 5. Consolidated code-ready block

```python
AP_050 = {
    "experiment_id": "ap_050",
    "data_set": "motion_area_2",

    # --- Detection (align with detector_config.json) ---
    "detector": {
        "model_path": "src/tests/analysis/batch_analysis/models/ssdlite_mobiledet_coco_qat_postprocess.tflite",
        "labels_path": "src/main/edge/models/coco_labels.txt",
        "input_size": (320, 320),
        "input_dtype": "uint8",
        "score_threshold": 0.35,
        "top_k": 5,
        "allowed_classes": ["stop sign"],
        "min_box_center_x": 0.5,
    },

    # --- Motion preprocess (batch — for computing motion scores) ---
    "motion_preprocess": {
        "roi": {"x_min": 0.25, "x_max": 0.75, "y_min": 0.55, "y_max": 0.95},
        "flow_scale": 0.5,
        "smoothing_window": 5,
        "crawl_motion_threshold": 2.5,
        "farneback": {
            "pyr_scale": 0.5,
            "levels": 3,
            "winsize": 15,
            "iterations": 3,
            "poly_n": 5,
            "poly_sigma": 1.2,
        },
    },

    # --- Live approach (winner_pf02) ---
    "approach": {
        "min_peak_pct": 0.25,
        "min_approach_s": 0.35,
        "max_approach_s": 12.0,
        "approach_start_peak_ratio": 0.1,
        "min_increasing_fraction": 0.5,
        "min_log_linear_r2": 0.3,
        "drop_within_s": 2.5,
        "drop_to_peak_ratio": 0.12,
        "post_drop_peak_ratio": 2.5,
        "post_drop_hold_s": 0.05,
    },

    # --- Live classification window ---
    "post_drop_window_s": 5.0,
    "stopped_motion_threshold": 0.6,  # live only (stopped_lo)

    # --- kNN stage 1: safe vs unsafe ---
    "knn1": {
        "k_neighbors": 3,
        "features": [
            "post_drop_mean_motion",
            "post_drop_min_motion",
            "post_drop_p95_motion",
            "post_drop_stop_fraction",
        ],
    },

    # --- kNN stage 2: rolling vs run-through ---
    "knn2": {
        "k_neighbors": 3,
        "features": [
            "post_drop_min_motion",
            "approach_area_sum_pct",
        ],
    },
}
```

---

## 6. Last recorded results (`results_summary`, 104 clips)

Run: `20260705T174249Z`

| Metric | Value |
|--------|-------|
| `clip_count` | 104 |
| `approach_accuracy_overall` | **98.0%** |
| `stage1_accuracy_overall` | **84.0%** |
| `stage2_accuracy_overall` | **91.3%** (46 eligible) |
| `knn_all_accuracy_overall` | **80.0%** (75 eligible — label correct when approach fired) |
| `e2e_accuracy_overall` | **83.3%** (102 eligible — full pipeline) |

**Per-class e2e:** complete-stop 75.9%, rolling-stop 76.9%, run-through 85.7%, unrelated 96.2%

**Metric definitions (workbook):**

| Column | Meaning |
|--------|---------|
| `approach_accuracy_overall` | Stop clips → approach fires; unrelated → silent |
| `knn_all_accuracy_overall` | Label correct **when approach fired** (legacy headline) |
| `e2e_accuracy_overall` | Full pipeline on **all** clips |

---

## 7. Implementation notes for edge code

1. **Two stop thresholds:** Batch motion JSON used **0.8** when scores were computed; **`ap_050` applies 0.6** only when computing `post_drop_stop_fraction` and other live kNN features. Do not re-run Farneback with 0.6 — match analysis by thresholding at classification time.

2. **Prefix approach:** Rerun grow→peak→drop on areas `[0..current_frame]` each frame. T₀ fires when the pattern first completes (usually shortly after the physical drop). See `project_management/diagrams/event_detection.md` §6.

3. **LOO training:** Live experiments train kNN leave-one-clip-out on the full tagged set. Pi deployment needs exported neighbor tables or equivalent — the workbook run does not embed trained weights in JSON.

4. **Clip set:** 104 clips in the tags sheet (includes extended clips 108+ once batch-processed). Every clip needs `evaluation/motion_area_2/data/*.areas.json` and `*.motion.json` before LOO or replay.

5. **Related code:**
   - Live sim: `batch_analysis/scripts/lib/live_motion_sim.py`
   - Feature extraction: `batch_analysis/scripts/lib/knn_feature_registry.py`
   - Run experiment: `live_motion_analysis/scripts/results/run_motion_experiment.py --experiment-id ap_050`
   - Replay: `live_motion_analysis/scripts/results/replay_clip_motion.py --experiment-id ap_050 --clip-id N`

6. **AT-3.4 comparison:** Integration bench at `src/tests/integration/at_3_4/` currently uses frozen `lm_19`-era configs (`post_drop_window_s: 5.0` matches `window_5`, but kNN feature sets and `stopped_lo` may differ). Update Pi configs explicitly when promoting `ap_050`.

---

## 8. `experiment_config` flat snapshot (from workbook)

Written on run `20260705T174249Z`:

| Key | Value |
|-----|-------|
| `det_model_path` | `src/tests/analysis/batch_analysis/models/ssdlite_mobiledet_coco_qat_postprocess.tflite` |
| `det_labels_path` | `src/main/edge/models/coco_labels.txt` |
| `det_input_width` / `det_input_height` | 320 / 320 |
| `det_input_dtype` | uint8 |
| `det_score_threshold` | 0.35 |
| `det_top_k` | 5 |
| `det_allowed_classes` | stop sign |
| `det_min_box_center_x` | 0.5 |
| `batch_roi_x_min` / `batch_roi_x_max` | 0.25 / 0.75 |
| `batch_roi_y_min` / `batch_roi_y_max` | 0.55 / 0.95 |
| `batch_flow_scale` | 0.5 |
| `batch_motion_smoothing_window` | 5 |
| `batch_stopped_motion_threshold` | 0.8 |
| `batch_crawl_motion_threshold` | 2.5 |
| `batch_farneback_pyr_scale` | 0.5 |
| `batch_farneback_levels` | 3 |
| `batch_farneback_winsize` | 15 |
| `batch_farneback_iterations` | 3 |
| `batch_farneback_poly_n` | 5 |
| `batch_farneback_poly_sigma` | 1.2 |
| `stopped_motion_threshold` | 0.6 |
| `post_drop_window_s` | 5 |
| `knn1_k_neighbors` | 3 |
| `knn2_k_neighbors` | 3 |
| `feature_set_stage1` | `post_drop_mean_motion, post_drop_min_motion, post_drop_p95_motion, post_drop_stop_fraction` |
| `feature_set_stage2` | `post_drop_min_motion, approach_area_sum_pct` |

Approach columns in the same row mirror §3.1 (`winner_pf02`).
