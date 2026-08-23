# TP-31 — Event metadata local storage

Integration harness for **TP-31** (`test.md`): trigger an unsafe stop-sign event
through the recording pipeline, persist the event graph to SQLite, and inspect
the most recent row.

## Run (on Pi)

From repo root, edge venv with **Coral USB TPU**, **ffmpeg**, and **buzzer on BCM 18**.
No USB camera (camera is mocked). Coral is required because `build_pipeline` always
loads the edgetpu detector model even though the stub skips live inference.

```bash
python src/tests/integration/tp_31/tp_31_event_metadata_local_storage.py
```

## What it checks

| Field | Source |
|-------|--------|
| Timestamp | `event.time` |
| Event type | auto `classification` → `rolling-stop` |
| Clip path | `clip.local_path` (MP4 under configured `src/main/data/clips`) |
| Stop duration | `approach_parameters.approach_duration_s` |
| Minimum motion | `knn_parameter` `post_drop_min_motion` (stage 1) |
| Detection confidence | `approach_parameters.log_linear_r2` (approach-fit; detector box score is not a schema column) |

SQLite is isolated at `src/tests/integration/tp_31/netrapi.db` (recreated each run).
Clips go to the configured data path, same as TP-23 / TP-26.

Classification is **stubbed** (`ROLLING_STOP`), same idea as TP-26 / TP-27.
Live in-car classify + beep + clip remains **TP-28**. Dummy insert/read without
the pipeline remains **TP-30**.
