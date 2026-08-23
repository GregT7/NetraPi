# Docker (local backend)

**Docker Desktop must be running** before any of these commands. If it is not, `docker build` and `docker compose` fail (`dockerDesktopLinuxEngine` / cannot connect to the engine).

From the repo root, `cd` into this directory first. Build context is the parent (`src/main`) so the image can copy `backend/` and `db/`.

## Build the image

```bat
cd src\main\backend
docker build -f Dockerfile -t netrapi-backend ..
```

## Compose (TP-37)

Starts FastAPI and a **temporary test** Postgres (not prod, not Supabase). Not used on Render. On start the image CMD runs `alembic upgrade head` against Compose `DATABASE_URL`, then uvicorn. Three DBs and apply steps: [cloud_architecture.md §4–5](../../../project_management/diagrams/cloud_architecture.md#4-three-databases).

```bat
cd src\main\backend
docker compose up --build
```

Health: http://127.0.0.1:8000/health
Docs (Compose only, not Render): http://127.0.0.1:8000/docs

Compose sets a dummy `NETRAPI_API_KEY` (`local-compose-netrapi-key`). Protected ingest routes need header `X-API-Key` with that value. `/health` does not.

Stop (same directory):

```bat
cd src\main\backend
docker compose down
```
