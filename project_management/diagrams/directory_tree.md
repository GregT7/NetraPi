# NetraPi — Target Directory Tree

> **Purpose:** Planned layout for application code and runtime data.  
> **Design ref:** [event_clip_pipeline.md](event_clip_pipeline.md) (single source of truth for the edge capture / clip pipeline)  
> **Scope:** Runnable code and tests only — not `project_management/`, not `test_scripts/`.

**Legend:** ✅ exists (implemented) · 📋 planned or stub only · 🏃 runtime-generated (gitignored; created when the app runs)

---

## Why everything lives under `src/`

This repo is a **monorepo**: edge (Pi), backend (FastAPI), and frontend (React) share one git root. Under **`src/`**:

- **`src/main/`** — all application code (`edge/`, `backend/`, `frontend/`, `data/`, `db/` as siblings)
- **`src/tests/`** — tests mirroring **`src/main/`**
- **Docs separate** — specs and diagrams stay in `project_management/`
- **Runtime output** — `src/main/data/clips/` (event clips) and `src/main/data/trips/` (segmented full-trip MP4s when enabled; gitignored)

---

## Top level

```
NetraPi/
├── compose.yml                        📋  Local dev only — `docker compose up` (not deployed)
└── src/
    ├── create_env.sh                  ✅  Linux/Pi venv + deps (numpy, opencv, pillow, tflite, scikit-learn, joblib)
    ├── create_env.bat                 ✅  Windows venv + deps (same; tflite may warn — expected)
    ├── main/                          📋  Application code — see full tree below
    └── tests/                         📋  Mirrors src/main/ — see full tree below
```

---

## `src/main/` — application code

No test directories under **`src/main/`** — all tests live in **`src/tests/`**.

```
src/main/
├── db/                                📋  Versioned SQL / migration scripts (in repo)
│   ├── edge/
│   │   └── migrations/                📋  SQLite on Pi (local event metadata)
│   └── cloud/
│       └── migrations/                📋  Postgres on Supabase (event metadata, S3 paths)
│
├── edge/                              ✅  Raspberry Pi — capture, detect, clip
│   ├── main.py                        ✅
│   ├── netrapi-edge.service           ✅  systemd unit for Pi (install to /etc/systemd/system/)
│   │
│   ├── config/                        ✅
│   │   ├── __init__.py                ✅
│   │   ├── types.py                   ✅
│   │   ├── loader.py                  ✅
│   │   ├── camera.json                ✅
│   │   ├── recording_manager.json     ✅
│   │   ├── preview.json               ✅
│   │   ├── detector.json              ✅
│   │   ├── event_manager.json         ✅
│   │   ├── approach_config.json       ✅  winner_pf02 thresholds
│   │   ├── motion_config.json         ✅  ROI, Farneback, stopped threshold, post_drop_window_s
│   │   ├── knn_config.json            ✅  feature lists, k, model_path per stage
│   │   ├── trip_recorder.json         ✅  optional full-trip segments (`--full-record`)
│   │   └── buzzer.json                ✅  GPIO pin, volume, pitch, duration, play_on flags
│   │
│   ├── models/                        ✅
│   │   ├── ssdlite_mobiledet_coco_qat_postprocess_edgetpu.tflite  ✅
│   │   ├── coco_labels.txt            ✅
│   │   ├── knn_stage1.joblib          ✅  serialized stage-1 kNN (no training set on Pi)
│   │   └── knn_stage2.joblib          ✅  serialized stage-2 kNN
│   │
│   └── netrapi/                       ✅
│       ├── __init__.py                ✅
│       ├── build.py                   ✅
│       ├── exceptions.py              ✅
│       ├── capture/
│       │   ├── __init__.py            ✅
│       │   ├── camera.py              ✅
│       │   └── preview.py             ✅
│       ├── buffer/
│       │   ├── __init__.py            ✅
│       │   ├── classification.py      ✅
│       │   ├── frame_record.py        ✅
│       │   └── frame_buffer.py        ✅
│       ├── detection/
│       │   ├── __init__.py            ✅
│       │   └── detector.py            ✅
│       ├── buzzer/
│       │   ├── __init__.py            ✅
│       │   └── buzzer.py              ✅  PWM beep on configured safe/unsafe events
│       ├── events/
│       │   ├── __init__.py            ✅
│       │   ├── event_manager.py       ✅  Watching / CollectPostDrop → DrivingEvent
│       │   ├── driving_event.py       ✅
│       │   ├── enums/                 ✅  StopSignEnum, EventPhase, Stage1/2Label
│       │   │   ├── __init__.py        ✅
│       │   │   ├── stop_sign_enum.py  ✅
│       │   │   ├── event_phase_enum.py ✅
│       │   │   └── knn_labels_enum.py ✅
│       │   ├── approach/              ✅  grow → peak → drop
│       │   │   ├── __init__.py        ✅
│       │   │   ├── detect.py          ✅
│       │   │   └── approach_drop_results.py ✅  ApproachDropEvent + diagnoses
│       │   └── classify/              ✅  motion / features / kNN
│       │       ├── __init__.py        ✅
│       │       ├── motion_score.py    ✅  Farneback + ROI motion sample
│       │       ├── features.py        ✅  stage-1 / stage-2 feature vectors
│       │       └── stop_classifier.py ✅  load joblib → StopSignEnum
│       └── recording/
│           ├── __init__.py            ✅
│           ├── recording_manager.py   ✅
│           ├── clip_package.py        ✅
│           ├── clip_result.py         ✅
│           ├── recorder.py            ✅
│           └── trip_recorder.py       ✅  segmented full-trip writer (CLI `--full-record`)
│
├── data/                              🏃  Runtime output (gitignored; not in repo)
│   ├── clips/                         🏃  event clips — `recording_manager.json` → clips_dir
│   └── trips/                         🏃  trip segments — `trip_recorder.json` → segments_dir
│
├── backend/                           📋  FastAPI on Render; only service with Docker
│   ├── Dockerfile                     📋
│   ├── requirements.txt               📋
│   └── app/
│       ├── __init__.py                📋
│       ├── main.py                    📋
│       ├── auth/
│       │   └── __init__.py            📋
│       └── routes/
│           └── __init__.py            📋
│
└── frontend/                          📋  React on Vercel; no Dockerfile
    ├── package.json                   📋
    └── src/
        ├── App.tsx                    📋
        ├── components/
        │   └── .gitkeep               📋
        └── api/
            └── .gitkeep               📋
```

### Deploy vs local dev

| Piece | Location | Deployed? |
|-------|----------|-----------|
| Backend Docker image | `src/main/backend/Dockerfile` | Yes → Render |
| Local backend stack | `compose.yml` (repo root) | No — dev machine only |
| Edge on Pi | `src/main/edge/netrapi-edge.service` + `main.py` | Yes — Pi (systemd) |
| Edge / test Python deps | `src/create_env.sh` (Pi) or `src/create_env.bat` (Windows) | Yes — creates `venv/` in cwd |
| Frontend | `src/main/frontend/` | Yes → Vercel |

No separate `deploy/` folder — each app keeps its own deploy artifact (`Dockerfile` in backend, `.service` in edge).

CI/CD (GitHub Actions) lives at repo root **`.github/workflows/`** when added.

### Database layout

| What | Where |
|------|--------|
| SQL migrations / schema scripts | `src/main/db/edge/migrations/`, `src/main/db/cloud/migrations/` |
| Backend Python DB code (session, models) | `src/main/backend/app/` when added — not mixed with SQL files |

---

## Edge class → file map

| Class | Path under `src/main/edge/` |
|-------|-------------------------------|
| `AppConfig`, `*Config` | `config/types.py`, `config/loader.py` |
| `ApproachConfig`, `MotionConfig`, `KnnConfig` | `config/types.py` |
| `Camera` | `netrapi/capture/camera.py` |
| `PreviewUI` | `netrapi/capture/` |
| `FrameRecord`, `FrameBuffer` | `netrapi/buffer/` |
| `Detector` | `netrapi/detection/detector.py` |
| `EventManager` | `netrapi/events/event_manager.py` |
| `DrivingEvent` | `netrapi/events/driving_event.py` |
| `StopSignEnum`, `EventPhase`, `Stage1Label`, `Stage2Label` | `netrapi/events/enums/` |
| approach detect helpers | `netrapi/events/approach/detect.py` |
| `ApproachDropEvent`, diagnosis types | `netrapi/events/approach/approach_drop_results.py` |
| motion / features helpers | `netrapi/events/classify/motion_score.py`, `features.py` |
| `StopClassifier` | `netrapi/events/classify/stop_classifier.py` |
| `Buzzer` | `netrapi/buzzer/buzzer.py` |
| `BuzzerConfig`, `BuzzerPlayOnConfig` | `config/types.py` |
| `RecordingManager` | `netrapi/recording/recording_manager.py` || `ClipPackage`, `Recorder`, `ClipResult` | `netrapi/recording/` |
| `TripRecorder` | `netrapi/recording/trip_recorder.py` |

---

## `src/tests/` — mirrors `src/main/`

Same folder shape as **`src/main/`**, with **`test_<module>.py`** (or `test_*.py`) where the source file exists.

**Mapping:** `src/main/edge/netrapi/buffer/frame_buffer.py` → `src/tests/unit/edge/netrapi/buffer/test_frame_buffer.py`

```
src/tests/
├── conftest.py                        ✅  adds src/main/edge to sys.path
├── venv/                              (local; gitignored — optional; create via `src/create_env.*`)
├── fixtures/
│   └── config/                        ✅  Sample JSON for loader/types tests
│       ├── camera.json                ✅
│       ├── recording_manager.json     ✅
│       ├── detector.json              ✅
│       ├── event_manager.json         ✅
│       ├── approach_config.json       ✅
│       ├── motion_config.json         ✅
│       ├── knn_config.json            ✅
│       ├── preview.json               ✅
│       ├── trip_recorder.json         ✅
│       └── buzzer.json                ✅
│
├── unit/
│   ├── edge/
│   │   ├── test_main.py               ✅  ↔ src/main/edge/main.py
│   │   ├── config/
│   │   │   ├── test_loader.py         ✅  ↔ loader.py (TP-17)
│   │   │   └── test_types.py          ✅  ↔ types.py (TP-17)
│   │   │
│   │   └── netrapi/                   ✅  ↔ src/main/edge/netrapi/
│   │       ├── test_build.py          ✅
│   │       ├── test_exceptions.py     ✅
│   │       ├── capture/
│   │       │   ├── test_camera.py     ✅
│   │       │   └── test_preview.py    ✅
│   │       ├── buffer/
│   │       │   ├── test_frame_record.py ✅
│   │       │   └── test_frame_buffer.py ✅
│   │       ├── detection/
│   │       │   └── test_detector.py         ✅
│   │       ├── buzzer/
│   │       │   └── test_buzzer.py           ✅
│   │       ├── events/
│   │       │   ├── test_event_manager.py    ✅
│   │       │   ├── test_driving_event.py    ✅
│   │       │   ├── test_stop_sign_enum.py   ✅
│   │       │   ├── test_approach.py         ✅
│   │       │   ├── test_motion_score.py     ✅
│   │       │   ├── test_features.py         ✅
│   │       │   └── test_stop_classifier.py  ✅
│   │       └── recording/
│   │           ├── test_recording_manager.py  ✅
│   │           ├── test_clip_package.py       ✅
│   │           ├── test_recorder.py           ✅
│   │           └── test_trip_recorder.py      ✅
│   │
│   ├── backend/
│   │   └── app/
│   │       └── test_main.py           📋  stub ↔ backend/app/main.py
│   │
│   └── frontend/
│       └── src/
│           └── App.test.tsx           📋  stub ↔ frontend/src/App.tsx
│
└── integration/
    ├── tp_26/                         ✅  stubbed event gate + clips
    ├── tp_27/                         ✅  stubbed event → real buzzer
    ├── tp_28/                         ✅  in-car E2E classify + beep + clip (full pipeline)
    ├── at_3_4/                        ✅  live motion + kNN bench
    └── edge/                          📋  Pi / hardware (optional, not default CI)
        └── .gitkeep                   📋
```

---

## Edge implementation order

1. `src/main/edge/config/` — types + loader ✅ (TP-17 tests in `src/tests/unit/edge/config/`)  
2. `src/main/edge/netrapi/buffer/` + `capture/` + `exceptions.py` ✅ (TP-18/TP-21 unit tests)  
3. `src/main/edge/netrapi/recording/` ✅ (TP-21/TP-23 unit tests)  
4. `src/main/edge/netrapi/detection/` + `events/` stub ✅ (TP-18/TP-19 unit tests)  
5. `src/main/edge/main.py` + `netrapi-edge.service` ✅  
6. `src/main/data/clips/` and `src/main/data/trips/` — 🏃 created on first write; keep `src/main/data/` in `.gitignore`  
7. Optional full-trip mode: `main.py --full-record` + `trip_recorder.json` (`segment_seconds`, default 300)  
8. Event port ✅ — approach / motion / features / stop_classifier + approach/motion/knn JSON + joblib models (design: [event_detection.md](event_detection.md))  
9. Buzzer ✅ — `netrapi/buzzer/` + `buzzer.json` (PWM beep on configured events; soft-fail GPIO)
