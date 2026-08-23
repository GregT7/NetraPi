# TP-37 — Local backend via Docker Compose

Build and start FastAPI from `src/main/backend/compose.yml` (next to the
Dockerfile, not the repo root). Hit `GET /health` (liveness + UTC `time`).
No S3/Supabase required. Compose sets `DATABASE_URL` to the local Postgres
container so a Windows host URL in `.env` is not used.

**Prereq:** Docker Desktop running. Compose overrides `DATABASE_URL` to the local Postgres container so a Windows host URL in `.env` is not used. The image CMD runs `alembic upgrade head` against that URL, then uvicorn.

```bat
python src\tests\integration\tp_37\tp_37_local_compose_boot.py
```

Or by hand from the backend directory:

```bat
cd src\main\backend
docker compose up --build
```

Then open http://127.0.0.1:8000/health . Stop with `docker compose down`
in that same directory.
