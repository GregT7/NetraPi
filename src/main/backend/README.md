# Backend FastAPI (Pi ingest)

## Run locally (this directory, not Docker)

From `src/main/backend`, with this folder’s venv and `requirements.txt` installed. Uses gitignored `.env` here (`DATABASE_URL` is the **Supabase** URI — not Compose Postgres). Stop Compose first if it already owns port 8000.

```bat
.\venv\Scripts\activate.bat
set PYTHONPATH=..;.
uvicorn app.main:app --reload
```

Health: http://127.0.0.1:8000/health  
Public clips: http://127.0.0.1:8000/api/public/clips  
Docs: http://127.0.0.1:8000/docs

---

Local uvicorn app for `GET /health` (TP-35), `POST /api/netrapi/master-config`, `POST /api/netrapi/driving-session`
(TP-34), `POST /api/netrapi/trip-segment`, and `POST /api/netrapi/driving-event`
(TP-36). JSON only. S3 routes (`s3-upload-url`, `confirm-s3-upload`, `s3-download-url`) need AWS
in this `.env`. Public Try-it-out playback (`GET /api/public/clips`, `POST /api/public/clip-download-url`)
needs AWS too and does **not** use `NETRAPI_API_KEY`. No Docker or Postgres required for the SQLite smokes.

Required env (process environment or gitignored `src/main/backend/.env`). Create that file with the keys below — there is no committed example file. Missing or empty `DATABASE_URL` or `NETRAPI_API_KEY` fails at startup. `DATABASE_URL` is the **Supabase** Postgres URI (TP-33 / TP-39 / TP-40 / TP-49 read this same key; they do not assemble a URI from `SUPABASE_DB_*`). Compose overrides it with local test Postgres and a dummy `NETRAPI_API_KEY`. The Pi SQLite URL lives in `src/main/edge/.env`, not here. The Pi holds the **same** device API key plus `NETRAPI_API_URL` (Render origin).

```text
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres?sslmode=require
NETRAPI_API_KEY=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-2
AWS_S3_BUCKET=
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

`CORS_ORIGINS` is optional locally (those two Vite origins are the default). On Render, add the Vercel origin so the browser can call the public mint. `POST /api/netrapi/*` requires header `X-API-Key` matching `NETRAPI_API_KEY`. `GET /health` and `/api/public/*` stay open. Swagger (`/docs`, `/redoc`, `/openapi.json`) is on for local uvicorn / Compose and off on Render (decision 59).

Alternatively from **repo root** (integration venv; Alembic `0001`–`0002` must already be applied to that `DATABASE_URL`; `master_config` id 1 must exist):

```bat
.\src\tests\integration\venv\Scripts\activate.bat
set PYTHONPATH=src\main;src\main\backend
uvicorn app.main:app --app-dir src\main\backend --reload
```

Pins: `src/main/backend/requirements.txt` (also installed by `src/create_env.bat` / `src/create_env.sh`).

Docker image + Compose (TP-37): [DOCKER.md](DOCKER.md). Docker Desktop must be running first.
