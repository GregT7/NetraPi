# TP-28 — In-car E2E classify + beep + clip

Fixed three-phase soak on the **fully integrated** edge pipeline (real Detector +
EventManager + Buzzer + Recorder). Same vibe as AT-3.4: SPACE to start each phase.

## Run (on Pi, in car)

Camera + Coral + buzzer on BCM 18. Edge venv:

```bash
python src/tests/integration/tp_28/tp_28_e2e_classify_beep_clip_integration.py
```

1. Click the preview window (focus).
2. **SPACE** to arm phase 1 → perform a **complete stop**.
3. **SPACE** → **rolling stop** (expect beep + clip).
4. **SPACE** → **run-through** (expect beep + clip).

Classifications before SPACE are ignored (no beep/clip).

## Phases

| Phase | Maneuver | Beep | Clip |
|-------|----------|------|------|
| 1/3 | `COMPLETE_STOP` | no | no |
| 2/3 | `ROLLING_STOP` | yes ≤ 10 s | MP4 under `clips_dir/tp_28/` |
| 3/3 | `RUN_THROUGH` | yes ≤ 10 s | MP4 under `clips_dir/tp_28/` |

## Evidence

- Console classify / latency / clip paths
- MP4s under the run’s `tp_28` clips subdirectory
