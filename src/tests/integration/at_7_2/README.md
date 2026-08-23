# AT-7.2 — Real camera + SPACE + stubbed events → deployed cloud

Dry-run before **AT-7.3**. Same three SPACE-armed phases as TP-28 / AT-7.3
(complete stop → rolling stop → run-through) with **live camera + preview**,
but EventManager is **stubbed**: SPACE injects the intended event. Persist /
upload still go through `RecordingManager` / `LocalStore` / `CloudIngest`.

Spec: [test.md](../../../../project_management/specs/test.md) § AT-7.2.

## Run (on Pi, parked / driveway)

Camera + Coral + buzzer on BCM 18. Edge venv.
`src/main/edge/.env` needs `NETRAPI_API_URL` / `NETRAPI_API_KEY` for Render.

```bash
python src/tests/integration/at_7_2/at_7_2_camera_stubbed_events_deployed_cloud.py
```

1. Click the preview window (focus).
2. **SPACE** → stub fires **complete stop** (no beep, no clip; metadata persists).
3. **SPACE** → stub fires **rolling stop** (beep + clip + upload).
4. **SPACE** → stub fires **run-through** (beep + clip + upload).

Nothing is injected before SPACE. Clips: `clips_dir/at_7_2/`.
Isolated SQLite: `src/tests/integration/at_7_2/netrapi.db` (recreated each run).
Short rolls (2 s pre / 2 s post) so the dry-run finishes quickly.

## Verify

### SQLite (on Pi)

```bash
python -c "import sqlite3; print(sqlite3.connect('src/tests/integration/at_7_2/netrapi.db').execute(\"SELECT e.id, ct.value, c.s3_stored, c.s3_key FROM event e LEFT JOIN clip c ON c.event_id=e.id JOIN classification cl ON cl.event_id=e.id AND cl.kind='auto' JOIN classification_type ct ON ct.id=cl.classification_type_id ORDER BY e.id\").fetchall())"
```

Expect three events: `complete-stop` (no clip / null s3), then `rolling-stop` and
`run-through` with `s3_stored=1`.

### Postgres (Supabase SQL editor)

On the laptop (no backend `.env` on the Pi). Isolated harness SQLite starts at
id 1 and **upserts** those ids in Postgres — prefer the `driving_session_id`
the script printed if you have it:

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

Expect three rows in order: `complete-stop` with `clip_id` / `s3_stored` / `s3_key`
null; `rolling-stop` and `run-through` with `s3_stored` true and keys like
`MMM-YYYY/driving_session_id_<id>/clips/clip-<id>.mp4`.

### S3

AWS console → `AWS_S3_BUCKET` → the two unsafe `clip.s3_key` objects. Complete
stop has no object.

### Render logs

https://dashboard.render.com → `netrapi` → Logs:

- `POST /api/netrapi/master-config` 200 (session start)
- `POST /api/netrapi/driving-session` 200
- `POST /api/netrapi/driving-event` 200 (three times)
- `POST /api/netrapi/s3-upload-url` 200 and `confirm-s3-upload` 200 (twice; unsafe only)

`GET /health` is Render probes. `operational-exception` only if ingest failed.

### Local clips / buzzer

- `clips_dir/at_7_2/` has **two** new MP4s (rolling + run-through).
- Hear beep on the two unsafe phases only.

## Progression

1. **AT-7.1** — mocked camera + stubbed event (no preview)
2. **AT-7.2** — this test (camera + preview + SPACE + stubbed events)
3. **AT-7.3** — live classify in car (real EventManager)
