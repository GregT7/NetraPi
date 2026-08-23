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

### Local clips / buzzer

- `clips_dir/at_7_2/` has **two** new MP4s (rolling + run-through).
- Hear beep on the two unsafe phases only.

### Optional Postgres / S3 / Render

Same laptop commands as [AT-7.1 README](../at_7_1/README.md).

## Progression

1. **AT-7.1** — mocked camera + stubbed event (no preview)
2. **AT-7.2** — this test (camera + preview + SPACE + stubbed events)
3. **AT-7.3** — live classify in car (real EventManager)
