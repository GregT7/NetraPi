# TP-53 — Unsafe event to cloud via deployed backend

Default path is a **harness** (no camera): `LocalStore` writes a rolling-stop
row + clip, then `CloudIngest` talks to Render. Confirms via local SQLite
`s3_stored` / `s3_key` after Render confirm. Same client the capture loop
uses.

Uses only `src/main/edge/.env` (`NETRAPI_API_URL`, `NETRAPI_API_KEY`).

```bash
source src/tests/integration/venv/bin/activate
python src/tests/integration/tp_53/tp_53_unsafe_event_deployed_backend.py
```

Default origin: https://netrapi.onrender.com

Optional live Postgres/S3 console check: AT-7.1 README (laptop).

## Optional in-car demo (buzzer)

Point Pi `src/main/edge/.env` at Render (`NETRAPI_API_URL`, same
`NETRAPI_API_KEY`), run the capture loop, trigger a rolling stop, confirm
beep + local clip.
