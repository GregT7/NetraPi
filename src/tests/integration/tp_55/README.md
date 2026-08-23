# TP-55 — Restart recovery then upload

Writes a local event + clip, drops the SQLite engine (simulated edge
restart), confirms the rows and MP4 are still there, then uploads through
Render. Uses only `src/main/edge/.env`. Confirms via local SQLite
`s3_stored` / `s3_key`.

```bash
source src/tests/integration/venv/bin/activate
python src/tests/integration/tp_55/tp_55_restart_recovery_upload.py
```
