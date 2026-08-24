# TP-57 — TPU smoke abort

A failed Coral TFLite dummy invoke aborts `main.py` before capture.
This harness mocks that failure (no Pi or Coral required) and checks
that the capture pipeline never starts.

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
python src/tests/integration/tp_57/tp_57_tpu_smoke_abort.py
```

## What to expect

- Script exit code **0**
- `main()` itself returns **1** (captured inside the harness)
- Printed checks, then `PASS: TPU abort exits 1 without capture`
- `build_pipeline` / keep-alive are not called
- No HDMI overlay and no leftover files
