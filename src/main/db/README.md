# Database

`edge/.env` is Pi SQLite (`netrapi.db` in this folder). `backend/.env` is Supabase Postgres. Do not put the Postgres URI in `edge/.env`.

From `src/main/db` with the backend venv on (`cloud` needs `psycopg2`):

```powershell
python apply.py sqlite          # apply head to SQLite
python apply.py cloud           # apply head to Supabase (reads backend/.env)
python apply.py current sqlite
python apply.py current cloud
```

`cloud` parses `DATABASE_URL` from `src/main/backend/.env` on disk. `sqlite` parses `src/main/edge/.env`. Leftover shell `DATABASE_URL` is ignored.

`upgrade` only adds missing revisions. It does not wipe rows. After `cloud`, restart local uvicorn. Render also runs `upgrade head` on deploy. Do not `downgrade` on Supabase.

## New revision

```powershell
python -m alembic -c alembic.ini revision -m "short description" --rev-id 0006
```

Edit `upgrade()` / `downgrade()` in `migrations/versions/`, then `python apply.py sqlite` and/or `python apply.py cloud`.

Compose / Render detail: [cloud_architecture.md §5](../../../project_management/diagrams/cloud_architecture.md#5-schema-migrations-local-vs-cloud).
