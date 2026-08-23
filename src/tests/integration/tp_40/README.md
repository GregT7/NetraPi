# TP-40 — Cloud metadata schema deployment

Uses backend `app.config.Settings` to load `DATABASE_URL` from gitignored
`src/main/backend/.env`, runs Alembic `upgrade head` against that Postgres
URL, then inspects `event` / `clip` / `trip_segment` (including `s3_key`).
No extra FastAPI route. Compose `DATABASE_URL` (throwaway test Postgres, not prod)
is not used.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_40\tp_40_cloud_metadata_schema.py
```

Needs the same `DATABASE_URL` as TP-39 (see `src/tests/integration/tp_33/README.md`).
This writes the shared schema to Supabase; it is safe to re-run (`upgrade head`
is idempotent once applied).
