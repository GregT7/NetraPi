# Cloud architecture

Stack for one-device MVS: the Pi keeps **production** SQLite + local files; FastAPI (Render, or Compose on the laptop) is the only process with AWS and Postgres credentials; private S3 holds media; **production** cloud metadata is Supabase Postgres. Compose Postgres is a throwaway laptop test DB only — not prod, not a copy of Supabase. Video never transits FastAPI. The Pi never holds permanent AWS or Postgres credentials (decision 22).

HTTP ingest payloads and the Pi↔API sequence live in [backend_api.md](backend_api.md). Tables live in [schema_design.md](schema_design.md). Edge capture/clip writing is [event_clip_pipeline.md](event_clip_pipeline.md). Public Try-it-out playback (rate limit + short signed GET + private bucket) lives in [frontend_playback.md](frontend_playback.md). Requirements: [mvs.md](../specs/mvs.md) R-6 / R-7 / R-8.

> **Tip:** Zoom the Markdown preview (Ctrl/Cmd + mouse wheel) or open this file on GitHub full-width. Diagrams use a dark theme for readability.

**Document map**

| Section | Contents |
|---------|----------|
| [§1 Purpose](#1-purpose) | What this file owns |
| [§2 Components](#2-components) | Who talks to what |
| [§3 Two environments](#3-two-environments) | Laptop Compose vs Render |
| [§4 Three databases](#4-three-databases) | Pi SQLite (prod) vs Compose Postgres (test) vs Supabase (prod) |
| [§5 Schema migrations](#5-schema-migrations-local-vs-cloud) | Alembic locally vs Supabase / Render |
| [§6 Credentials](#6-credentials) | Env vars by process |
| [§7 Drive vs Wi-Fi](#7-drive-vs-wi-fi) | When clips and trips go to S3 |
| [§8 Out of scope](#8-out-of-scope) | Frontend, two-way sync, S3 lifecycle |
| [§9 Related tests](#9-related-tests) | TP-32–57 |

---

## 1. Purpose

Give a single picture of the **cloud stack as a system**:

- Which process owns which store.
- Which env vars belong to the Pi vs the backend vs laptop admin.
- That there are **three databases**: Pi SQLite (local prod), Compose Postgres (temporary test), Supabase Postgres (cloud prod).
- How laptop Compose (test backend) differs from Render (prod backend).
- How the same Alembic tree is applied to each store.

This file is not a replica of the ingest API and not the ER diagram.

---

## 2. Components

FastAPI is the only process with AWS keys and a Postgres URL. The Pi writes **production** SQLite directly, then talks HTTP to FastAPI and PUTs bytes to a short-lived S3 URL. Production cloud metadata is Supabase. Compose Postgres is not in this picture (test only, [§4](#4-three-databases)). Frontend React on Vercel is still a later deploy; public Try-it-out playback is implemented in [frontend_playback.md](frontend_playback.md). Backend signed GET for ingest is TP-46.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryTextColor': '#e6e6e6', 'lineColor': '#6eb5ff', 'fontSize': '13px'}}}%%
flowchart LR
  subgraph edge [Pi]
    Pi[edge process]
    Sqlite["SQLite netrapi.db via edge/.env"]
    Files[local clips and trips]
  end
  subgraph backend [FastAPI]
    Api[Render or Compose]
  end
  subgraph cloud [Cloud stores]
    S3[private S3]
    Pg[Supabase Postgres prod]
  end
  Frontend[frontend Vercel]

  Pi -->|"edge/.env"| Sqlite
  Pi --> Files
  Pi -->|"JSON plus API key"| Api
  Pi -->|"presigned PUT"| S3
  Api -->|"engine from backend/.env"| Pg
  Api -->|"mint PUT URL"| S3
  Frontend -.->|"signed GET see frontend_playback"| S3
  Frontend -.->|"read metadata later"| Pg
```

---

## 3. Two environments

Laptop Compose is a **temporary test** of the Dockerized backend. It is not the Pi (local prod SQLite) and it is not production Supabase. Render is the deployed backend and talks to Supabase.

| | Laptop Compose | Render (deployed) |
| --- | --- | --- |
| FastAPI | `src/main/backend/compose.yml` | Docker image on Render |
| `DATABASE_URL` | Compose **overrides** to local test Postgres (decision 38 / 39 / 41). Host `src/main/backend/.env` is the Supabase URI and must not leak into the container. | Supabase Postgres — cloud prod (`src/main/backend/.env` / Render env) |
| Schema apply | Docker CMD `upgrade head` on boot ([§5.3](#53-local-compose-postgres-temporary-test-not-prod)) | same CMD against Supabase ([§5.5](#55-cloud-prod-render-boot)); first apply/inspect is TP-40 ([§5.4](#54-cloud-prod-first-apply-from-the-laptop-tp-40)) |
| S3 | real private bucket (backend AWS keys) | same bucket |
| Pi SQLite | not used (`src/main/edge/.env` is the Pi process only) | not used |
| `SUPABASE_DB_*` | unused (optional leftover keys; harnesses use `DATABASE_URL`) | unused |

Compose **overrides** host `src/main/backend/.env` `DATABASE_URL` so a Windows path, Pi SQLite URL, or leftover Supabase URI cannot leak into the container. Render does not use Compose. The Pi never loads `backend/.env`.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryTextColor': '#e6e6e6', 'lineColor': '#6eb5ff', 'fontSize': '13px'}}}%%
flowchart TB
  subgraph laptop [Laptop]
    ComposeApi[Compose FastAPI]
    ComposePg[Compose Postgres test only]
    Admin[admin scripts TP-33 TP-39 TP-40]
  end
  subgraph deployed [Deployed]
    RenderApi[Render FastAPI]
    Supabase[Supabase Postgres prod]
  end
  S3[private S3]
  Pi[Pi SQLite prod plus files]

  ComposeApi --> ComposePg
  ComposeApi --> S3
  Admin -->|"DATABASE_URL"| Supabase
  RenderApi -->|"DATABASE_URL"| Supabase
  RenderApi --> S3
  Pi -.->|"HTTP ingest when online"| ComposeApi
  Pi -.->|"HTTP ingest when online"| RenderApi
```

`DATABASE_URL` in `backend/.env` is laptop/admin connectivity (and schema apply) and the FastAPI / Render URI. It is never on the Pi.

---

## 4. Three databases

Same SQLModel tables in [`src/main/db`](../../src/main/db) (decision 37 / 41). One Alembic tree. **Three stores** — not two, and Compose is not a replica of Supabase.

| | Store | Role | Production? | Writer |
| --- | --- | --- | --- | --- |
| 1 | Pi SQLite (`src/main/db/netrapi.db`) | On-device source of truth while driving (offline-capable, M-5.20) | **Yes — local prod** | edge process: `init_engine()` with no URL loads `src/main/edge/.env` (required; no SQLite fallback). File still lives in `src/main/db/` |
| 2 | Compose Postgres | Throwaway laptop DB so Dockerized FastAPI can exercise the Postgres dialect | **No — temporary test only** | Compose FastAPI (`DATABASE_URL` override). Not deployed, not on the Pi, not associated with prod |
| 3 | Supabase Postgres | Cloud metadata copy of the row graph (ingest; prefer Pi integer PKs) | **Yes — cloud prod** | Render FastAPI: `init_engine(settings.database_url)` |

Production persistence is **1 + 3**. Compose (2) never receives Pi driving data as a sync target and is never copied into Supabase. `docker compose down -v` may wipe (2). The Pi does **not** call FastAPI to write SQLite.

[`migrations/env.py`](../../src/main/db/migrations/env.py) and runtime [`database.py`](../../src/main/db/database.py) load **`src/main/edge/.env`** for Pi SQLite (required; no fallback). They do **not** inherit a leftover shell `DATABASE_URL` from backend/Supabase. FastAPI Settings load **`src/main/backend/.env`** (Supabase URI). Apply steps: [§5](#5-schema-migrations-local-vs-cloud).

Do not point the Pi process at `backend/.env`. Do not run Alembic against Supabase from a shell that still has a leftover Compose URL, or the reverse. Alembic target is whichever `.env` that process loaded.

---

## 5. Schema migrations (local vs cloud)

One Alembic tree under [`src/main/db/migrations/`](../../src/main/db/migrations/). The target is whichever `.env` the **process that runs `upgrade`** loaded (`edge/.env` for Pi SQLite; Compose override for test Postgres; `backend/.env` / Render env for Supabase). FastAPI routes do not migrate. `upgrade head` is idempotent and does not wipe rows. Seed revision **0002** omits explicit primary keys (looks up FKs after insert) so PostgreSQL SERIAL sequences stay aligned with seeded rows.

| Store | Who runs `upgrade` | URL |
| --- | --- | --- |
| 1. Pi SQLite (local prod) | laptop or Pi shell ([`db/README.md`](../../src/main/db/README.md)) | `src/main/edge/.env` → `sqlite:///netrapi.db` (file is `src/main/db/netrapi.db`) |
| 2. Compose Postgres (test only) | Docker image **CMD** on every `compose up` (and `compose exec` to re-run) | Compose override `postgresql+psycopg2://netrapi_user:netrapi_pass@postgres:5432/netrapi_host` |
| 3. Supabase (cloud prod, first apply / inspect) | laptop admin, TP-40 | `DATABASE_URL` in `backend/.env` (not Compose, not Pi) |
| 3. Supabase (cloud prod, deployed) | same Docker **CMD** on Render boot | Render `DATABASE_URL` = Supabase URI (`postgresql+psycopg2://…?sslmode=require`) |

Compose Postgres is not published on the host and is not prod. Do not run Alembic from Windows against Compose using a leftover `.env` URL. Render does not use Compose.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryTextColor': '#e6e6e6', 'lineColor': '#6eb5ff', 'fontSize': '13px'}}}%%
flowchart TB
  Rev[migrations/versions]
  subgraph prodLocal [1 local prod]
    Sqlite[Pi SQLite]
  end
  subgraph testOnly [2 test only]
    ComposePg[Compose Postgres]
  end
  subgraph prodCloud [3 cloud prod]
    Supabase[Supabase Postgres]
  end
  Rev -->|"edge/.env SQLite"| Sqlite
  Rev -->|"Docker CMD or compose exec"| ComposePg
  Rev -->|"TP-40 backend/.env DATABASE_URL"| Supabase
  Rev -->|"Render CMD backend/.env DATABASE_URL"| Supabase
```

### 5.1 New revision (once, then apply everywhere)

Commands and file layout: [`src/main/db/README.md`](../../src/main/db/README.md).

1. Change [`models.py`](../../src/main/db/models.py) if the tables change.
2. From `src/main/edge` with venv active and **`src/main/edge/.env`** pointing at SQLite (not `backend/.env`):
   `python -m alembic -c ..\db\alembic.ini revision --autogenerate -m "short description" --rev-id 0003`
   Or `revision -m "..."` for an empty file you fill in.
3. Edit `upgrade()` / `downgrade()`. Review autogenerate output; do not autogenerate against live Supabase.
4. Apply in this order: **SQLite local prod** (§5.2) → **Compose test** (§5.3) → **Supabase cloud prod** (§5.4). Render boot (§5.5) is the production safety net.

### 5.2 Local prod: Pi / edge SQLite

This is the on-device production database. It is not Compose and not Supabase.

1. Activate the venv. `cd` to `src\main\edge` (or pass `-c src\main\db\alembic.ini` from repo root).
2. Confirm `src/main/edge/.env` is the SQLite URL (or you will migrate the wrong store).
3. Apply:

```bat
python -m alembic -c ..\db\alembic.ini upgrade head
python -m alembic -c ..\db\alembic.ini current
```

4. On Linux/Pi, use `../db/alembic.ini`. Wipe `src/main/db/netrapi.db` only if you want an empty file, then `upgrade head` again.

### 5.3 Local: Compose Postgres (temporary test, not prod)

Docker Desktop must be running. This Postgres exists only on the Compose network for laptop testing (decision 38 / 39 / 41). It is not production and is not associated with Supabase. The image CMD is `alembic upgrade head && uvicorn` ([`Dockerfile`](../../src/main/backend/Dockerfile)).

1. `cd src\main\backend`
2. Start stack (applies pending revisions, then serves):

```bat
docker compose up --build
```

3. Confirm `GET http://127.0.0.1:8000/health` and that logs show Alembic reaching head. If Alembic fails, uvicorn never starts.
4. Re-apply or inspect without recreating containers:

```bat
docker compose exec backend python -m alembic -c /netrapi/db/alembic.ini current
docker compose exec backend python -m alembic -c /netrapi/db/alembic.ini upgrade head
```

5. Stop: `docker compose down` (same directory). Volumes keep Postgres data unless you `down -v`.

Compose **overrides** host `backend/.env` `DATABASE_URL`. This path never writes to Supabase (prod) or Pi SQLite.

### 5.4 Cloud prod: first apply from the laptop (TP-40)

Use this before Render exists, and any time you want to inspect Supabase from the laptop. Needs TP-33 / TP-39 credentials in gitignored `src/main/backend/.env` (`DATABASE_URL`). Never put that URI on the Pi.

1. Activate the integration venv from repo root.
2. Run:

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_40\tp_40_cloud_metadata_schema.py
```

3. The script loads `DATABASE_URL` from `backend/.env`, sets the Alembic override, runs `upgrade head`, then checks `alembic_version` plus event/clip/trip tables.
4. Safe to re-run. It does not start FastAPI and does not use Compose `DATABASE_URL`.

Manual equivalent (only if you must): set the Alembic override (or process `DATABASE_URL`) to that same Supabase URI, then `python -m alembic -c src\main\db\alembic.ini upgrade head`. Do not put a Supabase URI in `edge/.env`.

Do not `downgrade` on Supabase as a routine step.

### 5.5 Cloud prod: Render boot

Same image as Compose. Render env `DATABASE_URL` is the **Supabase** URI (`postgresql+psycopg2://…?sslmode=require`), not Compose test credentials.

1. Confirm TP-40 has been applied at least once (or accept that first boot will create the schema).
2. Set Render `DATABASE_URL` to the same Supabase URI as `backend/.env`.
3. Deploy. On every start, CMD runs `upgrade head` against that URL, then uvicorn.
4. If a new revision is in the image, a redeploy applies it. If Alembic fails, the service does not come up.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': { 'primaryTextColor': '#e6e6e6', 'lineColor': '#6eb5ff', 'fontSize': '13px'}}}%%
sequenceDiagram
  participant Dev as laptop
  participant Compose as Compose backend
  participant Pg as Compose Postgres test
  participant TP40 as TP-40
  participant Sb as Supabase prod
  participant Render as Render backend

  Dev->>Compose: docker compose up
  Compose->>Pg: alembic upgrade head
  Compose->>Compose: uvicorn
  Dev->>TP40: python tp_40_...py
  TP40->>Sb: alembic upgrade head
  Dev->>Render: deploy image
  Render->>Sb: alembic upgrade head
  Render->>Render: uvicorn
```

---

## 6. Credentials

Env vars belong to a **process**, not to the `db` package.

| Variable | Pi | Compose FastAPI | Render FastAPI | Laptop admin / TP-33 39 40 |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | `src/main/edge/.env` → local SQLite (never `backend/.env`) | Compose Postgres override (test only) | `src/main/backend/.env` / Render env = Supabase URI | `backend/.env` `DATABASE_URL` (TP-33 / 39 / 40 / 49) |
| `NETRAPI_API_KEY` | yes (same value Render verifies) | Compose dummy override | `backend/.env` / Render env | no |
| `NETRAPI_API_URL` | yes (Render origin) | unused | unused | no |
| `SUPABASE_DB_*` | never | unused for inserts | unused | unused (optional; TP-33/39/40/49 use `DATABASE_URL`) |
| AWS keys + bucket | never | yes | yes | TP-38 |
| Device API key | yes (Sprint 6 TP-42) | verifies it | verifies it | no |

The Pi authenticates to FastAPI and receives a short-lived S3 PUT URL. It does not write Supabase and does not keep permanent AWS credentials.

---

## 7. Drive vs Wi-Fi

Event clips may PUT during the drive when online (small, infrequent). Trip segments wait for Wi-Fi. Detail: [backend_api.md §3.1](backend_api.md#31-when-files-go-to-s3-data-budget). Sequence of HTTP calls: [backend_api.md §4](backend_api.md#4-sequence).

| What | During the drive | Later, Wi-Fi |
| --- | --- | --- |
| Event clip | local file + `driving-event` JSON; then presigned PUT if online | retry PUT if the in-drive upload failed |
| Trip segment | local file + `trip-segment` JSON prime (`s3_stored` null). No S3 PUT | `CloudIngest.drain_trip_segments` / `main.py --drain`: one file at a time, presigned PUT + confirm |
| Local MP4 cleanup | leave files on disk | `--delete-uploaded` (already in S3) or `--delete-all`; `confirm-local-delete` (S3 objects stay) |

---

## 8. Out of scope

Do not design these here (ingest and MVS cloud path stay as above):

- List/filter events and Vercel project setup (M-7.14, R-9). Public clip playback is [frontend_playback.md](frontend_playback.md). Ingest signed GET is TP-46.
- Two-way sync (Postgres → SQLite)
- S3 time-based retention / lifecycle (decision 29)
- Multipart video on FastAPI (bytes go Pi → S3)
- Permanent AWS or Postgres credentials on the Pi

---

## 9. Related tests

| Tests | Role |
| --- | --- |
| TP-32–40 | Provision S3 + Supabase (cloud prod); Compose boot (test Postgres, not prod); backend reaches S3/Supabase; TP-40 Alembic on Supabase |
| TP-41 | Edge pipeline persist: `trip_segment` rows in Pi SQLite |
| TP-42–49 | API key; S3 PUT/GET; `driving-event` → Postgres; hotspot upload; local E2E |
| TP-50–56 | Render deploy + edge ↔ deployed backend E2E (no frontend) |

Public Try-it-out playback: [frontend_playback.md](frontend_playback.md). Backend ingest signed GET is TP-46.
