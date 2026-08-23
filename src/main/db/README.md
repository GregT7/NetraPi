# Database

Pi SQLite (local prod) commands below. Compose Postgres is throwaway test only; Supabase is cloud prod. Apply steps: [cloud_architecture.md §4–5](../../../project_management/diagrams/cloud_architecture.md#4-three-databases).

Run these from `src/main/edge` with the venv active.

```powershell
# get to right location if not already there (cd below assumes you're in root dir)
# can also run from root:
# python -m alembic -c src\main\db\alembic.ini upgrade head
cd src\main\edge

# apply anything not applied yet (creates netrapi.db if missing)
python -m alembic -c ..\db\alembic.ini upgrade head

# where this DB is in the revision chain
python -m alembic -c ..\db\alembic.ini current
python -m alembic -c ..\db\alembic.ini history

# undo last data revision (tables stay)
python -m alembic -c ..\db\alembic.ini downgrade 0001

# undo everything (tables gone)
python -m alembic -c ..\db\alembic.ini downgrade base
```

On Linux/Pi, use `../db/alembic.ini`.

`upgrade head` only runs new steps. It does not delete existing rows. Wipe the file only if you want a brand-new empty DB, then `upgrade head` again.

Create gitignored `src/main/edge/.env` with `DATABASE_URL=sqlite:///netrapi.db`. There is no committed example file. `DATABASE_URL` is required — there is no SQLite fallback. Relative sqlite paths resolve to `netrapi.db` in **this** directory (`src/main/db/`), not next to the env file. The edge process reads `edge/.env` only — not `src/main/backend/.env`. Alembic uses process `DATABASE_URL` when set (Compose, Render, TP-40), otherwise `edge/.env`.

When the Pi talks to FastAPI, put `NETRAPI_API_URL` (Render origin, or a local uvicorn origin for TP-49) and `NETRAPI_API_KEY` in the same `edge/.env` file. `main.py` copies those into the process environment once at start; ingest then snapshots them. After each local SQLite write, `CloudIngest` POSTs JSON and PUTs event clips with a backend-issued URL (no AWS keys on the Pi). Session start find-or-creates a config snapshot (`POST /master-config`) so `driving_session.master_config_id` exists in Postgres; unchanged live JSON reuses Alembic seed id 1. After confirm, it sets `s3_key` / `s3_stored` on the local clip row. Trip files stay JSON-primed during the drive; `main.py --drain-trips` PUTs them later and then sets those flags on the local `trip_segment` row. `main.py --delete-uploaded-local` / `--delete-all-local` unlinks finished local MP4s and sets `init_local_deleted` (cloud via `confirm-local-delete`); S3 objects stay. Local persist sets `clip.file_size_bytes` and finished `trip_segment.file_size_bytes` from the file on disk. Missing URL/key means local-only. Ingest calls send header `X-API-Key`.

## New revision

```powershell
# empty file (data inserts, or you will write SQL yourself)
python -m alembic -c ..\db\alembic.ini revision -m "short description" --rev-id 0004

# or have alembic diff models.py against live db and create a revision to make the 2 equal
python -m alembic -c ..\db\alembic.ini revision --autogenerate -m "short description" --rev-id 0004
```

Alembic writes `migrations/versions/0004_short_description.py` and sets:

- `revision = "0004"` — this file’s id
- `down_revision = "0003"` — parent (whatever `current` is)

Then edit `upgrade()` / `downgrade()`, and run `upgrade head`.

| File | Role |
|------|------|
| `models.py` | table definitions |
| `database.py` | engine + session; loads `edge/.env` |
| `writes.py` | local session/event/clip/trip inserts |
| `config_snapshot.py` | fingerprint live edge JSON; find-or-create `master_config` (reuse if unchanged) |
| `alembic.ini` | Alembic config (real URL is set in `migrations/env.py`) |
| `migrations/versions/` | revision scripts (`0001` tables, `0002` lookup + config rows, `0003` trip `file_size_bytes`) |
