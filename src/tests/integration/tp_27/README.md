# TP-27 — Stubbed event → real buzzer

Integration harness for **TP-27** (`test.md`): build the real edge pipeline
(including the real `Buzzer`), mock the camera, inject mock `DrivingEvent`s, and
confirm audible feedback for unsafe stop-sign types within **10 seconds**.

## Run (on Pi)

From repo root, **edge venv** with **buzzer on BCM 18** and **Coral USB TPU plugged in**.

No USB camera needed (camera is mocked). Coral **is** required: `build_pipeline` always
loads the edgetpu `.tflite` model via `Detector.load()`, even though the stub sets
`needs_detection=False` so inference is never run. Without the TPU you typically see
`edgetpu-custom-op` / prepare errors.

The venv needs `rpi-lgpio` (provides `RPi.GPIO`). System `/usr/bin/python3` may already have it, but a Python 3.9 edge venv usually does not see apt’s package:

```bash
# once, inside the activated edge venv:
pip install rpi-lgpio
```

(`src/create_env.sh` installs this automatically on new envs.)

```bash
python src/tests/integration/tp_27/tp_27_stubbed_event_buzzer_integration.py
```

Timing-only (skip “Did you hear the beep?” prompts):

```bash
python src/tests/integration/tp_27/tp_27_stubbed_event_buzzer_integration.py --assume-heard
```

## Scenarios

| Event | Expect |
|-------|--------|
| `ROLLING_STOP` | `buzzer.beep` within 10 s; operator hears tone |
| `RUN_THROUGH` | same |
| `COMPLETE_STOP` | **no** beep (`play_on.safe=false`) |

## How it works

1. Builds the normal pipeline (`build_pipeline`) — loads the Coral edgetpu detector model.
2. Replaces the camera with `_FakeCamera` (synthetic black frames).
3. Replaces `EventManager` with `_DeferredEventStub` (`needs_detection=False` — no live inference).
4. Wraps the real `Buzzer.beep` to record evaluate→beep latency, then forwards to GPIO PWM.
5. Arms each mock event on the next idle lap; stops soon after the beep (or after a few laps for the no-beep case).

Does **not** require real stop-sign classification or a live camera. Full in-car classify + beep + clip is **TP-28** (`src/tests/integration/tp_28/`).
