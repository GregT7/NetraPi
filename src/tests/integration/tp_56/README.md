# TP-56 — Deployed system smoke

Minimal evidence without a frontend: Render `/health`, one harness event
through `CloudIngest`, then local SQLite `s3_stored` / `s3_key`. Buzzer is
optional (TP-53 in-car demo).

Uses only `src/main/edge/.env` (`NETRAPI_API_URL`, `NETRAPI_API_KEY`). Does
**not** load `src/main/backend/.env`.

```bash
source src/tests/integration/venv/bin/activate
python src/tests/integration/tp_56/tp_56_deployed_system_smoke.py
```

Optional laptop Postgres/S3 inspection: same commands as AT-7.1 README.
