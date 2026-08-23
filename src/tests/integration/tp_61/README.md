# TP-61 — Drain clips, trips, or both

`--drain-trips` requires `clips`, `trips`, or `both`. Drain wakes Render
via `/health`, uploads that target, and does not start capture.
`--delete-after-drain {clips,trips,both}` unlinks local MP4s already in S3
after a successful drain. This harness mocks Render and uses a temp SQLite
DB for the scoped-delete check (no live upload).

## Activate venv (from repo root)

Windows (cmd):

```bat
src\tests\integration\venv\Scripts\activate.bat
```

Windows (PowerShell):

```powershell
src\tests\integration\venv\Scripts\Activate.ps1
```

Linux / Raspberry Pi:

```bash
source src/tests/integration/venv/bin/activate
```

If `venv` is missing, create it first from `src/tests/integration`:
Windows `..\..\create_env.bat` / Linux `../../create_env.sh`.

## Run

```bash
python src/tests/integration/tp_61/tp_61_drain_clips_trips_both.py
```

## What to expect

- Exit code **0**
- `--drain-trips` with no target → argparse error
- `--delete-after-drain` without `--drain-trips` → exit 1
- `clips` uploads clips only; `trips` uploads trips only; `both` is clips
  then trips then delete
- Failed `/health` wake skips drain and delete
- Scoped `target=clips` deletes the clip MP4 and leaves the trip file
- `PASS: drain targets, wake-before-upload, scoped delete-after-drain`
- Temp sqlite under `tp_61/_tmp` is removed on success
