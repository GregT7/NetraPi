# TP-48 — Presigned upload over hotspot/mobile data

From a **client on hotspot/cellular**, hit a reachable FastAPI origin:
`s3-upload-url` → PUT to S3 (no AWS keys) → `confirm-s3-upload`.

The backend must be reachable from that network (LAN `uvicorn --host 0.0.0.0`,
a tunnel, or a deployed preview). Loopback (`127.0.0.1`) is rejected unless
you set `NETRAPI_TP48_ALLOW_LOOPBACK=1` for a dry run.

Needs gitignored `src/main/backend/.env` (`NETRAPI_API_KEY`, AWS) plus:

```text
set NETRAPI_API_URL=http://192.168.0.12:8000
```

```bat
.\src\tests\integration\venv\Scripts\activate.bat
set NETRAPI_API_URL=http://YOUR-LAN-OR-TUNNEL:8000
python src\tests\integration\tp_48\tp_48_hotspot_presigned_upload.py
```

The script HEADs S3 afterward with backend credentials (inspection only).
The upload path itself uses only `X-API-Key` and the issued PUT URL.
