# TP-44 — Stable S3 object key generation

Two authenticated `POST /api/netrapi/s3-upload-url` calls for the same clip
id return the same `object_key` (`MMM-YYYY/driving_session_id_{id}/clips/clip-{id}.mp4`). JSON only.

Needs AWS in gitignored `src/main/backend/.env` so the backend can mint URLs
(no object is uploaded).

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_44\tp_44_stable_s3_object_key.py
```
