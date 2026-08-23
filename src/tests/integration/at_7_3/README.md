# AT-7.3 — In-car three-maneuver E2E to deployed cloud

Same SPACE-armed drive as TP-28 (complete stop → rolling stop → run-through)
on the **live** pipeline (real camera, Detector, EventManager). Persist and
upload go through `RecordingManager` / `LocalStore` / `CloudIngest` (Pi SQLite
+ Render + S3 + Postgres).

Run **AT-7.2** first (camera + SPACE + stubbed events dry-run).

Spec: [test.md](../../../../project_management/specs/test.md) § AT-7.3.

## Run (on Pi, in car)

Camera + Coral + buzzer on BCM 18. Edge venv.
`src/main/edge/.env` needs SQLite `DATABASE_URL` plus `NETRAPI_API_URL` /
`NETRAPI_API_KEY` for Render.

```bash
python src/tests/integration/at_7_3/at_7_3_incar_e2e_deployed_cloud.py
```

1. Click the preview window (focus).
2. **SPACE** → **complete stop** (no beep, no clip; metadata persists).
3. **SPACE** → **rolling stop** (beep + clip + upload).
4. **SPACE** → **run-through** (beep + clip + upload).

Classifications before SPACE are ignored. Clips: `clips_dir/at_7_3/`.
SQLite is the Pi file from `DATABASE_URL` (usually `src/main/db/netrapi.db`).
The harness runs `alembic upgrade head` on startup (does **not** wipe existing
rows). Script prints all three event types; unsafe rows include `s3_key`.

Optional trip files: this harness leaves `--full-record` off. To also record
trip segments, run `python src/main/edge/main.py --full-record` as a separate
drive, then `python src/main/edge/main.py --drain-trips` on Wi-Fi.

## Verify

### SQLite (on Pi)

Latest session events (LEFT JOIN so complete-stop without a clip still shows):

```bash
python -c "import sqlite3; print(sqlite3.connect('src/main/db/netrapi.db').execute(\"SELECT e.id, ct.value, c.s3_stored, c.s3_key FROM event e LEFT JOIN clip c ON c.event_id=e.id JOIN classification cl ON cl.event_id=e.id AND cl.kind='auto' JOIN classification_type ct ON ct.id=cl.classification_type_id ORDER BY e.id DESC LIMIT 3\").fetchall())"
```

Expect three rows including `complete-stop` (null clip/s3) plus two uploaded unsafe
types. Clips only for rolling/run-through under default `record_safe_events=false`.

### Postgres (Supabase SQL editor)

On the laptop (no backend `.env` on the Pi). Use the `driving_session_id` the
script printed if you have it — Pi SQLite autoincrements, so this is **not**
usually session 1:

```sql
SELECT
  e.id AS event_id,
  e.driving_session_id,
  ct.value AS event_type,
  c.id AS clip_id,
  c.s3_stored,
  c.s3_key,
  c.file_size_bytes
FROM event e
JOIN classification cl
  ON cl.event_id = e.id AND cl.kind = 'auto'
JOIN classification_type ct
  ON ct.id = cl.classification_type_id
LEFT JOIN clip c
  ON c.event_id = e.id
WHERE e.driving_session_id = 1  -- replace with the printed session id
ORDER BY e.id;
```

If you did not keep the session id, latest session that has all three types:

```sql
SELECT
  e.id AS event_id,
  e.driving_session_id,
  ct.value AS event_type,
  c.id AS clip_id,
  c.s3_stored,
  c.s3_key
FROM event e
JOIN classification cl
  ON cl.event_id = e.id AND cl.kind = 'auto'
JOIN classification_type ct
  ON ct.id = cl.classification_type_id
LEFT JOIN clip c
  ON c.event_id = e.id
WHERE e.driving_session_id = (
  SELECT e2.driving_session_id
  FROM event e2
  JOIN classification cl2
    ON cl2.event_id = e2.id AND cl2.kind = 'auto'
  JOIN classification_type ct2
    ON ct2.id = cl2.classification_type_id
  GROUP BY e2.driving_session_id
  HAVING COUNT(*) FILTER (WHERE ct2.value = 'complete-stop') >= 1
     AND COUNT(*) FILTER (WHERE ct2.value = 'rolling-stop') >= 1
     AND COUNT(*) FILTER (WHERE ct2.value = 'run-through') >= 1
  ORDER BY e2.driving_session_id DESC
  LIMIT 1
)
ORDER BY e.id;
```

Expect three rows: `complete-stop` with `clip_id` / `s3_stored` / `s3_key` null;
`rolling-stop` and `run-through` with `s3_stored` true and keys like
`MMM-YYYY/driving_session_id_<id>/clips/clip-<id>.mp4`. Types must match what you actually drove
(live classifier, not a stub).

### S3

AWS console → bucket from `src/main/backend/.env` `AWS_S3_BUCKET` → the two
unsafe `clip.s3_key` objects from the query. Complete stop has **no** object.
Object sizes should match `file_size_bytes`. Do not need AWS keys on the Pi.

### Render logs

https://dashboard.render.com → `netrapi` → Logs for this drive:

- `POST /api/netrapi/master-config` 200 (session start)
- `POST /api/netrapi/driving-session` 200
- `POST /api/netrapi/driving-event` 200 (**three** times: complete-stop JSON with
  no clip, then two unsafe events)
- `POST /api/netrapi/s3-upload-url` 200 and `confirm-s3-upload` 200 (**twice**;
  rolling-stop and run-through only)

`GET /health` is Render probes. `operational-exception` only if ingest failed.

### Local clips / buzzer

- `clips_dir/at_7_3/` has **two** new MP4s (rolling + run-through), none for complete stop.
- Hear beep on the two unsafe phases only.
