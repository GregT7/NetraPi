# AT-3.4 — Live approach + motion + classification bench

Pi integration test: four **keypress-started** phases (~30s each) with AT-3.3-style HUD, per-frame approach detection, a **5s post-drop motion window**, two-stage sklearn kNN classification, and HDMI banners.

Spec: [test.md](../../../project_management/specs/test.md) § AT-3.4.

## Config provenance

Frozen configs under `config/` come from **ap_050** (`window_5_motion_area_2_stopped_lo_k3_min_area`). Numbers and feature lists: [`ap_050_config_reference.md`](../../../project_management/diagrams/ap_050_config_reference.md). Reference run `20260705T174249Z` (stage1 **84.0%**, e2e **83.3%**, 104 clips).

Offline analysis under `src/tests/analysis/` is **local-only** (gitignored). Re-running prep needs that tree on disk; committed `config/*.json` + `*.joblib` are enough for the Pi bench.

Resolved literals (no profile IDs at runtime):

| File | Origin |
|------|--------|
| `approach_config.json` | `winner_pf02` — `min_peak_pct=0.25`, … |
| `motion_config.json` | `stopped_lo` — live `stopped_motion_threshold=0.6`, motion_area_2 ROI/flow |
| `metrics_config.json` | `window_5` — `post_drop_window_s=5.0` |
| `detector_config.json` | `score_threshold=0.35`, `min_box_center_x=0.5` |
| `knn_config.json` | `k3` stage-1 (`runtime4`) + `k3_min_area` stage-2 (`min_area`) |
| `knn_stage1.joblib`, `knn_stage2.joblib` | Trained on local `data/` with **per-frame T₀** anchor |
| `provenance.json` | Full metadata written by prep script |

### Two-stage kNN (ap_050)

| Stage | k | Features |
|-------|---|----------|
| 1 | 3 | `post_drop_mean_motion`, `post_drop_min_motion`, `post_drop_p95_motion`, `post_drop_stop_fraction` |
| 2 (unsafe only) | 3 | `post_drop_min_motion`, `approach_area_sum_pct` |

Shared cycle logic lives in [`at_3_4_pipeline.py`](at_3_4_pipeline.py).

## One-time prep (laptop)

Requires batch-processed `motion_area_2` cache (`*.areas.json` / `*.motion.json`).

```bash
python src/tests/integration/at_3_4/prepare_at_3_4_config.py
```

This copies training clips into `data/`, writes `config/*.json`, fits kNN joblib files, and writes `provenance.json`.

Sync `config/` (and optionally `data/` for audit) to the Pi if they are not in your deployment bundle.

## Pi prerequisites

- Raspberry Pi + USB camera + Coral Edge TPU (TP-12)
- `tflite_runtime`, OpenCV, **scikit-learn**, **joblib**
- HDMI display for preview (`--show-window`)

```bash
source <your-venv>/bin/activate
pip install scikit-learn joblib
```

## In the car

```bash
python src/tests/integration/at_3_4/at_3_4_live_motion_classification_benchmark.py \
  --show-window --write-status
```

### Operator flow

1. **Phase 1/4 — Baseline drive** (SPACE): normal driving ~30s. HUD only (no motion/kNN). Establishes baseline FPS.
2. **Phase 2/4 — Complete stop** (SPACE): full stop at a sign.
3. **Phase 3/4 — Rolling stop** (SPACE): rolling stop.
4. **Phase 4/4 — Run-through** (SPACE): run through without stopping.

During phases 2–4:

- **Green banner** when approach is detected (`APPROACH DETECTED @ t=…s`).
- **Blue banner** if classified **complete-stop** (safe).
- **Red banner** if classified **rolling-or-run-through** (unsafe).
- Both banners clear **10s** after classification; phase continues until 30s.
- **One** approach + classification cycle per phase: on approach, the area prefix is snapshotted and cleared so the grow-peak-drop pattern cannot re-fire; `cycle_locked` after classification prevents a second cycle.

Press `q` or Esc to quit early.

## Clip replay (laptop debug)

Same **per-frame approach → 5s motion window → two-stage kNN** pipeline as the live bench, but on stored MP4 clips with CPU TFLite (no Pi camera / Coral required).

```bash
python src/tests/integration/at_3_4/at_3_4_replay_clip_classification.py --clip-id 10 --show-window
python src/tests/integration/at_3_4/at_3_4_replay_clip_classification.py \
  --clip-path vids/unsafe_events/clips/clip_010_....mp4 --output replay_out.mp4
```

## Outputs

| Path | Contents |
|------|----------|
| `logs/at_3_4_summary_<stamp>.json` | Pass/fail + per-phase stats |
| `logs/last_bench_status.json` | Same summary when `--write-status` |
| `run_data/<stamp>/events.jsonl` | Approach, stage1/stage2 features, classification, phase end |
| `run_data/<stamp>/manifest.json` | Run metadata + provenance snapshot |

## Pass criteria (automated)

- Phases 2–4 each log **exactly one** approach and **exactly one** classification.
- Motion-window **average** FPS loss ≤ **40%** vs phase-1 baseline FPS (per-lap min is diagnostic only).
- Phases 2–4 `approach_ms_p95` ≤ **33ms** (baseline phase excluded).
- **Label correctness** vs your driving intent: manual review of `events.jsonl` and overlay (not auto-failed).

## What this does not do

- No `netrapi/` / `EventManager` changes
- No swappable experiments at runtime (ap_050 frozen in prep)
- No audible buzzer
