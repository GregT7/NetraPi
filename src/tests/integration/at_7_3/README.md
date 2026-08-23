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
SQLite is the Pi file `src/main/db/netrapi.db` (not wiped). Schema must already
be at Alembic head (`python -m alembic -c src/main/db/alembic.ini upgrade head`
from repo root, or from `src/main/edge` with `../db/alembic.ini`). Script prints
all three event types; unsafe rows include `s3_key`.

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

### Postgres / S3 / Render

Same optional laptop commands as [AT-7.1 README](../at_7_1/README.md).

### Local clips / buzzer

- `clips_dir/at_7_3/` has **two** new MP4s (rolling + run-through), none for complete stop.
- Hear beep on the two unsafe phases only.
