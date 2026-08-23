# AT-7.1 — Mocked Pi pipeline to deployed cloud

Real `build_pipeline` / `RecordingManager.run_loop` / `LocalStore` / `CloudIngest`.
Camera and EventManager are mocked. The harness does **not** seed rows or POST
ingest APIs itself.

Spec: [test.md](../../../../project_management/specs/test.md) § AT-7.1.

## Run (on Pi)

Edge venv, Coral plugged in, buzzer on BCM 18. No USB camera.
`src/main/edge/.env` needs `NETRAPI_API_URL` + `NETRAPI_API_KEY` (Render).

```bash
python src/tests/integration/at_7_1/at_7_1_mocked_pipeline_deployed_cloud.py
```

Isolated SQLite: `src/tests/integration/at_7_1/netrapi.db` (recreated each run).
That file starts at id 1; if Postgres already has those ids, ingest **upserts**.
Clips: `clips_dir/at_7_1/`. Script prints `event id` and `s3_key`.

## Verify

Use the printed event id in place of `EVENT_ID` if you want a single row.
These commands use the **latest** event.

### SQLite (on Pi)

```bash
python -c "import sqlite3; print(sqlite3.connect('src/tests/integration/at_7_1/netrapi.db').execute('SELECT e.id, c.s3_stored, c.s3_key FROM event e JOIN clip c ON c.event_id=e.id ORDER BY e.id DESC LIMIT 1').fetchall())"
```

Expect one row, `s3_stored=1`, key like `device-1/YYYY-MM-DD/clip-<id>.mp4`.

### Postgres (Supabase SQL editor)

On the laptop with Supabase access (no backend `.env` on the Pi):

```sql
SELECT e.id, c.s3_stored, c.s3_key
FROM event e
JOIN clip c ON c.event_id = e.id
ORDER BY e.id DESC
LIMIT 1;
```

Expect the same id / key as SQLite, `s3_stored=true`.

### S3

AWS console → bucket from `src/main/backend/.env` `AWS_S3_BUCKET` → object
matching `clip.s3_key`. Do not need AWS keys on the Pi.

### Render logs

https://dashboard.render.com → `netrapi` service → Logs. For this run you want:

- `POST /api/netrapi/master-config` 200
- `POST /api/netrapi/driving-session` 200
- `POST /api/netrapi/driving-event` 200
- `POST /api/netrapi/s3-upload-url` 200
- `POST /api/netrapi/confirm-s3-upload` 200

`GET /health` 200 lines are Render probes, not the test. There is **no**
`operational-exception` POST unless ingest actually failed.
