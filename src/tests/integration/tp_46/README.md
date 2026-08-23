# TP-46 — Private object access via signed GET

PUT a tiny clip via `s3-upload-url` (no AWS keys on the client), confirm it,
then:

1. GET the unsigned `https://{bucket}.s3.{region}.amazonaws.com/{key}` URL
   (must be 401/403 — private bucket).
2. Authenticated `POST /api/netrapi/s3-download-url` with `{ "clip_id": ... }`.
3. GET the returned URL; body must match the uploaded bytes.

Needs AWS in gitignored `src/main/backend/.env` (same as TP-43 / TP-47).

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_46\tp_46_signed_get.py
```
