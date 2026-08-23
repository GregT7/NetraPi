# TP-52 — Deployed backend API-key authentication

Same contract as TP-42, against Render. `GET /health` has no key.
`POST /api/netrapi/driving-event` without a key or with a wrong key is
401. A valid `X-API-Key` can prime a session and persist an event.

Needs `NETRAPI_API_KEY` (and optional `NETRAPI_API_URL`) in
`src/main/edge/.env` matching Render. Does **not** use backend `.env`.

```bash
source src/tests/integration/venv/bin/activate
python src/tests/integration/tp_52/tp_52_deployed_api_key_auth.py
```

Default origin: https://netrapi.onrender.com
