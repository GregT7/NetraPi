# NetraPi — Target Directory Tree

> **Purpose:** Planned layout for application code and runtime data.  
> **Design ref:** [event_clip_pipeline.md](event_clip_pipeline.md) (edge capture / clip pipeline); [backend_api.md](backend_api.md) (Pi ingest FastAPI); [cloud_architecture.md](cloud_architecture.md) (three DBs: Pi SQLite prod, Compose Postgres test, Supabase prod; Compose vs Render)  
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
└── src/
    ├── create_env.sh                  ✅  Linux/Pi venv + deps (numpy, opencv, pillow, tflite, scikit-learn, joblib, sqlmodel, alembic, psycopg2-binary, fastapi, uvicorn, httpx)
    ├── create_env.bat                 ✅  Windows venv + deps (same; tflite may warn — expected)
    ├── main/                          📋  Application code — see full tree below
    └── tests/                         📋  Mirrors src/main/ — see full tree below
```

---

## `src/main/` — application code

No test directories under **`src/main/`** — all tests live in **`src/tests/`**.

```
src/main/
├── db/                                ✅  Shared SQLModel package (Pi SQLite local prod; Compose Postgres test-only; same models for Supabase cloud prod)
│   ├── __init__.py                    ✅
│   ├── alembic.ini                    ✅  Alembic config (url always overridden in env.py)
│   ├── database.py                    ✅  engine + session; loads edge/.env (SQLite PRAGMA foreign_keys=ON)
│   ├── writes.py                      ✅  local session / event / clip / trip inserts
│   ├── config_snapshot.py             ✅  fingerprint + find-or-create master_config from edge JSON
│   ├── models.py                      ✅  operational + config tables
│   ├── netrapi.db                     🏃  SQLite file (gitignored; created by alembic upgrade head)
│   └── migrations/                    ✅  one Alembic tree; dialect from engine URL
│       ├── env.py                     ✅  SQLModel metadata; loads edge/.env or process DATABASE_URL
│       ├── script.py.mako             ✅
│       └── versions/                  ✅  0001 schema + 0002 classification_type / edge-json snapshot + 0003 trip file_size_bytes + 0004 health_config
│
├── edge/                              ✅  Raspberry Pi — capture, detect, clip
│   ├── README.md                      ✅  how to run capture, boot health, online/offline, drain
│   ├── main.py                        ✅
│   ├── .env                           🏃  gitignored; DATABASE_URL=sqlite:///netrapi.db (file lands in db/); NETRAPI_API_URL + NETRAPI_API_KEY for ingest
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
│   │   ├── buzzer.json                ✅  GPIO pin, volume, pitch, duration, play_on flags
│   │   └── health.json                ✅  boot probes, Render wait, keep-alive, health log path
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
│       ├── backend_auth.py            ✅  apply_edge_env once; snapshot X-API-Key + URL from process env
│       ├── cloud_ingest.py            ✅  SQLite row → FastAPI JSON; master-config before session; clip PUT on event; trip PUT on drain
│       ├── health.py                  ✅  boot probes, HDMI overlay, keep-alive, online/offline
│       ├── local_cleanup.py           ✅  unlink local MP4s; confirm-local-delete
│       ├── local_store.py             ✅  thin adapter: RecordingManager → db/writes.py + config snapshot
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
│   ├── Dockerfile                     ✅  image for Render and local Compose
│   ├── compose.yml                    ✅  local only — `docker compose up` from this dir (context `src/main`)
│   ├── requirements.txt               ✅  fastapi / uvicorn / httpx / boto3 / db pins
│   ├── .env                           🏃  gitignored; DATABASE_URL (Supabase URI) + NETRAPI_API_KEY + AWS
│   ├── README.md                      ✅  local uvicorn / env keys (create `.env` by hand)
│   ├── DOCKER.md                      ✅  Docker Desktop prereq; `docker build` + Compose (TP-37)
│   └── app/
│       ├── __init__.py                ✅  puts src/main on path for `db`
│       ├── main.py                    ✅  lifespan + routers
│       ├── config.py                  ✅  pydantic-settings: DATABASE_URL; NETRAPI_API_KEY; optional AWS + SUPABASE_DB_*
│       ├── s3.py                      ✅  presign PUT/GET + HEAD; keys MMM-YYYY/driving_session_id_{id}/{clips|trips}/{clip|trip}-{id}.mp4
│       ├── auth/                      ✅  device API key (TP-42)
│       │   ├── __init__.py            ✅
│       │   └── api_key.py             ✅  X-API-Key on /api/netrapi/*
│       └── routes/                    ✅  Pi ingest — [backend_api.md](backend_api.md)
│           ├── __init__.py            ✅
│           ├── health.py              ✅  GET /health (TP-35)
│           ├── ready.py               ✅  GET /api/netrapi/ready (TP-59)
│           ├── master_config.py       ✅  POST /api/netrapi/master-config (find-or-create snapshot)
│           ├── driving_session.py     ✅  POST /api/netrapi/driving-session (TP-34)
│           ├── trip_segment.py        ✅  POST /api/netrapi/trip-segment (JSON prime)
│           ├── driving_event.py       ✅  POST /api/netrapi/driving-event (TP-36 / nested children)
│           ├── operational_exception.py ✅  POST /api/netrapi/operational-exception
│           └── s3_upload.py           ✅  POST s3-upload-url, confirm, s3-download-url, confirm-local-delete
│
└── frontend/                          ✅  Vite + React + TS + Tailwind SPA; no Dockerfile
    ├── package.json                   ✅
    ├── vite.config.ts                 ✅  Tailwind + Vitest; tests under src/tests/unit/frontend
    ├── vercel.json                    ✅  SPA rewrite; Vercel project not connected yet
    ├── README.md                      ✅
    ├── index.html                     ✅
    ├── public/
    │   └── gifs/
    │       └── .gitkeep               ✅  drop approach.gif etc. later
    └── src/
        ├── main.tsx                   ✅
        ├── App.tsx                    ✅  single-page layout
        ├── index.css                  ✅  Tailwind v4
        ├── test-setup.ts              ✅  Testing Library jest-dom
        ├── components/
        │   ├── SiteNav.tsx            ✅
        │   ├── Hero.tsx               ✅
        │   ├── Overview.tsx           ✅  stacked Mermaid hardware + software
        │   ├── MermaidDiagram.tsx     ✅  mermaid.render + Iconify logos
        │   ├── mermaidCharts.ts       ✅
        │   ├── mermaidSetup.ts        ✅
        │   ├── diagramIconPacks.ts    ✅  Iconify subset for diagrams
        │   ├── HowItWorks.tsx         ✅  stub
        │   ├── Demo.tsx               ✅  YouTube placeholder + Results
        │   ├── ClusterScatter.tsx     ✅  2D kNN neighborhood sketch
        │   ├── clusterData.ts         ✅
        │   ├── TryItOut.tsx           ✅  table stub (no S3)
        │   └── Links.tsx              ✅
        └── api/
            └── .gitkeep               ✅
```

### Deploy vs local dev

| Piece | Location | Deployed? |
|-------|----------|-----------|
| Backend Docker image | `src/main/backend/Dockerfile` | Yes → Render |
| Local backend stack | `src/main/backend/compose.yml` | No — dev machine only |
| Edge on Pi | `src/main/edge/netrapi-edge.service` + `main.py` | Yes — Pi (systemd) |
| Edge / test Python deps | `src/create_env.sh` (Pi) or `src/create_env.bat` (Windows) | Yes — creates `venv/` in cwd |
| Frontend | `src/main/frontend/` | Later → Vercel (scaffold only; project not connected) |

No separate `deploy/` folder — each app keeps its own deploy artifact (`Dockerfile` in backend, `.service` in edge).

CI/CD (GitHub Actions) lives at repo root **`.github/workflows/`** when added.

### Database layout

| What | Where |
|------|--------|
| Shared SQLModel models + engine | `src/main/db/models.py`, `src/main/db/database.py`, `src/main/db/writes.py`, `src/main/db/config_snapshot.py` |
| Local / Pi database | SQLite — `src/main/db/netrapi.db` (gitignored); URL from `src/main/edge/.env` |
| Cloud database | Postgres on Supabase (backend); same models; URI in `src/main/backend/.env` |
| Migrations | `src/main/db/migrations/` (one Alembic tree; target is whichever `.env` that process loaded) |

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
| `RecordingManager` | `netrapi/recording/recording_manager.py` |
| `ClipPackage`, `Recorder`, `ClipResult` | `netrapi/recording/` |
| `TripRecorder` | `netrapi/recording/trip_recorder.py` |
| `LocalStore` | `netrapi/local_store.py` |

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
│       ├── buzzer.json                ✅
│       └── health.json                ✅
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
│   │       ├── test_boot_health.py    ✅  ↔ health.py (TP-57–60)
│   │       ├── test_cloud_ingest.py   ✅  ↔ cloud_ingest.py
│   │       ├── test_local_cleanup.py  ✅  ↔ local_cleanup.py
│   │       ├── test_backend_auth.py   ✅  ↔ backend_auth.py
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
│   ├── db/
│   │   ├── conftest.py                ✅  sys.path + sqlite tmp file
│   │   ├── test_database.py           ✅  ↔ db/database.py
│   │   ├── test_writes.py             ✅  ↔ db/writes.py
│   │   ├── test_config_snapshot.py    ✅  ↔ db/config_snapshot.py (fingerprint reuse + new snapshot)
│   │   ├── test_models.py             ✅  ↔ db/models.py
│   │   └── test_migrations.py         ✅  Alembic upgrade head + seed
│   │
│   ├── backend/
│   │   ├── conftest.py                ✅  sys.path + in-memory DATABASE_URL
│   │   └── app/
│   │       ├── test_main.py           ✅  ↔ backend/app/main.py
│   │       ├── test_api_key.py        ✅  ↔ auth/api_key.py (401 vs /health open)
│   │       ├── test_health.py         ✅  ↔ routes/health.py
│   │       ├── test_s3.py             ✅  ↔ s3.py object keys
│   │       └── routes/
│   │           ├── test_ready.py              ✅  ↔ ready.py (SELECT 1 + HeadBucket)
│   │           ├── test_driving_session.py ✅  ↔ driving_session.py (mocked session)
│   │           ├── test_master_config.py   ✅  ↔ master_config.py (find-or-create)
│   │           ├── test_driving_event.py   ✅  ↔ driving_event.py (nested children)
│   │           ├── test_trip_segment.py    ✅  ↔ trip_segment.py
│   │           ├── test_operational_exception.py ✅  ↔ operational_exception.py
│   │           └── test_s3_upload.py       ✅  ↔ s3_upload.py
│   │
│   └── frontend/
│       ├── tsconfig.json              ✅  IDE types; packages resolve from frontend/node_modules
│       └── src/
│           └── App.test.tsx           ✅  ↔ frontend/src/App.tsx (Vitest via frontend package)
│
└── integration/
    ├── tp_26/                         ✅  stubbed event gate + clips
    ├── tp_27/                         ✅  stubbed event → real buzzer
    ├── tp_28/                         ✅  in-car E2E classify + beep + clip (full pipeline)
    ├── tp_31/                         ✅  pipeline persist rolling-stop → SQLite
    ├── tp_34/                         ✅  FastAPI driving-session → SQLite
    ├── tp_35/                         ✅  FastAPI GET /health
    ├── tp_36/                         ✅  FastAPI driving-event → SQLite
    ├── tp_37/                         ✅  Docker Compose boot (`src/main/backend/compose.yml`)
    ├── tp_38/                         ✅  FastAPI → private S3 PUT/HEAD
    ├── tp_39/                         ✅  FastAPI Settings → Supabase SELECT 1
    ├── tp_40/                         ✅  Alembic upgrade head → Supabase schema inspect
    ├── tp_41/                         ✅  trip_segment local insert
    ├── tp_42/                         ✅  X-API-Key on /api/netrapi/*; /health open
    ├── tp_43/                         ✅  s3-upload-url + client PUT (no AWS keys)
    ├── tp_44/                         ✅  stable S3 object keys
    ├── tp_45/                         ✅  driving-event → Supabase Postgres
    ├── tp_46/                         ✅  unsigned GET denied; s3-download-url GET
    ├── tp_47/                         ✅  confirm-s3-upload sets s3_key / s3_stored
    ├── tp_48/                         ✅  presigned PUT+confirm from hotspot client
    ├── tp_49/                         ✅  local SQLite event → FastAPI → S3 + Postgres
    ├── tp_50/                         ✅  production Dockerfile build + GET /health
    ├── tp_51/                         ✅  Render deploy reachable (`/health`)
    ├── tp_52/                         ✅  deployed X-API-Key on `driving-event`
    ├── tp_53/                         ✅  SQLite event → Render CloudIngest → S3 + Postgres
    ├── tp_54/                         ✅  TP-53 sqlite vs Postgres vs S3 keys
    ├── tp_55/                         ✅  sqlite restart then Render upload
    ├── tp_56/                         ✅  deployed smoke (`/health` + one event)
    ├── tp_57/                         ✅  TPU smoke abort (mocked main)
    ├── tp_58/                         ✅  offline Wi-Fi / internet (mocked boot)
    ├── tp_59/                         ✅  deployed GET /api/netrapi/ready
    ├── tp_60/                         ✅  online boot + keep-alive → offline
    ├── tp_61/                         ✅  --drain-trips clips|trips|both + delete-after-drain
    ├── tp_62/                         ✅  health.json snapshot (Alembic 0004)
    ├── at_7_1/                        ✅  mocked Pi pipeline → Render persist + ingest
    ├── at_7_2/                        ✅  camera + SPACE + stubbed events → cloud (dry-run)
    ├── at_7_3/                        ✅  in-car three-maneuver E2E → SQLite + S3 + Postgres
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
7. Optional full-trip mode: `main.py --full-record` + `trip_recorder.json` (`segment_seconds`, default 300). Wi‑Fi trip upload: `main.py --drain-trips {clips,trips,both}`. After a successful drain: `--delete-after-drain {clips,trips,both}`. Standalone local MP4 cleanup: `--delete-uploaded-local` or `--delete-all-local`.  
8. Event port ✅ — approach / motion / features / stop_classifier + approach/motion/knn JSON + joblib models (design: [event_detection.md](event_detection.md))  
9. Buzzer ✅ — `netrapi/buzzer/` + `buzzer.json` (PWM beep on configured events; soft-fail GPIO)
