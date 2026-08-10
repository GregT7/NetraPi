# AT-3.3 — Continuous approach live benchmark (Pi FPS + overlay)

Pi-only harness: measure **loop FPS cost** of running `diagnose_approach_drop` every lap vs baseline (capture + EdgeTPU infer only). Shows **HDMI overlay** when approach is detected so you can validate in the car without the record → apartment → analyze cycle.

Spec: [test.md](../../../project_management/specs/test.md) § AT-3.3.

## Prerequisites

- Raspberry Pi with USB camera + Coral Edge TPU
- `tflite_runtime`, OpenCV, analysis lib deps (same as batch analysis scripts)
- Repo checked out on the Pi

## In the car (recommended)

```bash
python src/tests/integration/at_3_3/at_3_3_continuous_approach_live_benchmark.py \
  --duration-seconds 120 --show-window --write-status
```

1. **Phase 1 (~60s):** baseline — no approach call.
2. **Phase 2 (~60s):** same loop + one `diagnose_approach_drop` per lap on the growing area series.
3. Drive past a stop sign during phase 2; overlay should show **`APPROACH DETECTED @ t=…s`**.
4. Press `q` to stop early (logged as warning).

## Read results

Console prints `=== AT-3.3 summary ===` with:

| Field | Meaning |
|-------|---------|
| `loop_fps_baseline` / `loop_fps_approach` | End-to-end laps per second |
| `fps_delta_pct` | FPS cost of approach |
| `approach_ms_p95` | Time inside diagnose (95th percentile) |
| `approach_detected` | Whether phase 2 saw a pattern |
| `first_detect_time_s` | When overlay fired |

Files in `logs/`:

- `at_3_3_metrics_<stamp>.csv` — periodic snapshots
- `at_3_3_summary_<stamp>.json` — full summary
- `last_bench_status.json` — same summary when `--write-status` (quick `cat` after parking)

**Pass criteria:** `fps_delta_pct <= 33%`, `approach_ms_p95 <= 33ms`, and `approach_detected = true` (phase 2 must see a live approach).

## Dev replay (laptop — not a FPS benchmark)

Sanity-check approach logic on a preprocessed areas file (requires local `src/tests/analysis/`, which is gitignored):

```bash
python src/tests/integration/at_3_3/at_3_3_continuous_approach_live_benchmark.py \
  --replay-areas src/tests/analysis/batch_analysis/evaluation/motion_area_1/data/clip_002_*.areas.json
```

## Approach config

Uses the pf_02 winner thresholds (`min_peak_pct=0.25`). See [`ap_050_config_reference.md`](../../../project_management/diagrams/ap_050_config_reference.md).

## What this does not do

- No changes to `netrapi/` or `EventManager`
- No motion/kNN classify (approach detection only)
