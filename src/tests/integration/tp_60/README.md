# TP-60 — Online boot and keep-alive drop to offline

Mocks Wi-Fi, internet, Render `/health`, and `/ready` so boot is online.
`main()` starts keep-alive. Three failed pings disable cloud ingest for the
rest of the process. No live Render or Coral required.

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
python src/tests/integration/tp_60/tp_60_online_keepalive_offline.py
```

## What to expect

- Exit code **0**
- Boot result `mode=online`, `abort=False`
- `main()` calls `build_pipeline(..., cloud_enabled=True)` and starts KeepAlive
- After three failed pings, `cloud_ingest` is None and the give-up reason
  mentions 3 failures
- `PASS: online boot; three keep-alive fails drop to offline`
- No leftover files
