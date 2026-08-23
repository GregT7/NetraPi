# TP-35 — Local FastAPI health

`GET /health`. Body is `{ "status": "ok", "time": "<UTC>" }`.
The harness prints that JSON. No Docker, S3, or Supabase.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_35\tp_35_local_fastapi_health.py
```

Needs `fastapi==0.115.8` and `httpx==0.27.2` (see `src/create_env.bat`).
Leaves `src/tests/integration/tp_35/netrapi.db` for inspection.
