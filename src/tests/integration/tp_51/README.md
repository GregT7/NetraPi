# TP-51 — Backend deployment to hosting environment

Hits the live Render service. Pass = `GET /health` returns
`{"status":"ok","time":"..."}`. Origin from `src/main/edge/.env`
`NETRAPI_API_URL`, else https://netrapi.onrender.com (Render may take
~30–180s to wake). Does **not** use `src/main/backend/.env`.

```bash
python src/tests/integration/tp_51/tp_51_backend_deployment.py
```

`GET /` is 404 on purpose (no root route). Use `/health`.
Render **Health Check Path** should be `/health` so a failed check is not a successful deploy (M-10.22, M-10.23).
