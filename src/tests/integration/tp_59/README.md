# TP-59 — Authenticated `/ready` (Postgres + S3)

Live check against Render. `GET /health` has no key. `GET /api/netrapi/ready`
without a key or with a wrong key is 401. A valid `X-API-Key` returns 200
(database + S3 ok) or 503 with per-layer status.

Needs `NETRAPI_API_KEY` (and optional `NETRAPI_API_URL`) in
`src/main/edge/.env` matching Render. Does **not** use backend `.env`.

Forced DB/S3 503 paths are covered by
`src/tests/unit/backend/app/routes/test_ready.py`.

If this harness gets **404** on `/api/netrapi/ready`, the current Render
revision predates that route — redeploy the backend, then rerun.

## Activate venv (from repo root)

Windows (cmd):

```bat
src\tests\integration\venv\Scripts\activate.bat
```

Windows (PowerShell):

```powershell
src\tests\integration\venv\Scripts\Activate.ps1
```

Linux / Raspberry Pi:

```bash
source src/tests/integration/venv/bin/activate
```

If `venv` is missing, create it first from `src/tests/integration`:
Windows `..\..\create_env.bat` / Linux `../../create_env.sh`.

## Run

```bash
python src/tests/integration/tp_59/tp_59_ready_postgres_s3.py
```

Default origin: https://netrapi.onrender.com (first call may wait up to ~180s
while Render wakes; per-request timeouts are retried).

## What to expect

- Exit code **0**
- `GET /health` → 200 `{ "status": "ok", ... }`
- `GET /api/netrapi/ready` no key / wrong key → **401**
- Valid key → **200** with `database` and `s3` both `ok`, or **503** with
  per-layer `error` plus `detail`
- `PASS: /health open; /api/netrapi/ready requires X-API-Key and reports DB+S3`
- No local files written
