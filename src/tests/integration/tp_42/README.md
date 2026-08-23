# TP-42 — Edge API-key authentication

`GET /health` without `X-API-Key` succeeds. `POST /api/netrapi/driving-session`
without a key or with a wrong key returns 401. The same POST with a valid
`X-API-Key` succeeds. No Docker, S3, or Supabase.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_42\tp_42_edge_api_key_auth.py
```

Needs `fastapi==0.115.8` and `httpx==0.27.2` (see `src/create_env.bat`).
Leaves `src/tests/integration/tp_42/netrapi.db` for inspection.
