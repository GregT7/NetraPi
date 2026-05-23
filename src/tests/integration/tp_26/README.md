# TP-26 — Stubbed event gate + clip extraction

Integration harness for **TP-26** (`test.md`): stub-inject all three `StopSignEnum` types and verify clip policy under `record_safe_events`.

## Run (on Pi)

From repo root, edge venv with camera + ffmpeg (+ Coral if `VERIFY_TPU` stays true):

```bash
python src/tests/integration/tp_26/tp_26_stubbed_event_gate_clips_integration.py
```

## Scenarios

| Event | `record_safe_events` | Expect |
|-------|----------------------|--------|
| `ROLLING_STOP` | false | MP4 written |
| `RUN_THROUGH` | false | MP4 written |
| `COMPLETE_STOP` | false | no clip |
| `COMPLETE_STOP` | true | MP4 written |

Unsafe always records (independent of the flag). Safe (`COMPLETE_STOP`) only when the flag is true.

## How it works

1. Builds the normal pipeline (`build_pipeline`).
2. Replaces `EventManager` with `_DeferredEventStub` (returns `None` until armed).
3. For expect-clip cases: fill `pre_buffer` (~2 s), arm the stub with the scenario event, let the idle gate call `begin_clip`, then post-roll → `write_clip` (same path as TP-23).
4. For the no-clip case: one idle lap with `COMPLETE_STOP` + `record_safe_events=false`; assert `clip_active` stays false and no new MP4.

Does **not** require real stop-sign classification. Gate-only smoke (no MP4) remains **AT-2.2**.
