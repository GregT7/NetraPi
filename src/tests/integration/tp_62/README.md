# TP-62 — Health settings snapshot

`health.json` is snapshotted as `health_config` (Alembic 0004) and included
in the master-config fingerprint. Unchanged JSON reuses seed id 1. A timeout
change inserts a new snapshot. Uses a temp SQLite DB (no Render, no Pi).

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
python src/tests/integration/tp_62/tp_62_health_config_snapshot.py
```

## What to expect

- Exit code **0**
- After `alembic upgrade head`, seed `master_config` id 1 has a
  `health_config` row (`render_wait_s=90`)
- Fingerprint of live edge JSON matches that seed, so find-or-create reuses
  id 1
- Copying config and setting `render_wait_s` to 42 inserts a second
  `master_config` + `health_config`
- `PASS: health_config seeded, fingerprint reuse, change inserts row`
- Temp files under `tp_62/_tmp` are removed on success
