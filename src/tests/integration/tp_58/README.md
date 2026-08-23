# TP-58 — Offline when Wi-Fi is missing or internet fails

No Wi-Fi association is an informational offline start. Associated but
no internet is a loud offline fallback. Both still start capture with
cloud ingest off. This harness mocks the probes (no live radio required).

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
python src/tests/integration/tp_58/tp_58_offline_wifi_internet.py
```

## What to expect

- Exit code **0**
- Step 1: no association → offline, not abort, not a persisted error
- Step 2: associated, no internet → offline, loud persisted log (SSID named)
- Step 3: `main()` starts capture with `cloud_enabled=False`, no keep-alive
- `PASS: missing Wi-Fi / no internet start offline capture`
- No leftover files
