# TP-36 — Local FastAPI driving-event

`POST /api/netrapi/driving-event` JSON (no file) into SQLite. Prime a
session first (same shape as TP-34). Nested clip keeps `s3_key` /
`s3_stored` null; auto classification uses Alembic `0002` type ids.

The harness prints the event POST JSON. No Docker, S3, or Supabase.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_36\tp_36_local_fastapi_driving_event.py
```

Needs `fastapi==0.115.8` and `httpx==0.27.2` (see `src/create_env.bat`).
Leaves `src/tests/integration/tp_36/netrapi.db` for inspection.
