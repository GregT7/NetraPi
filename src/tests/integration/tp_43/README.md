# TP-43 — s3-upload-url issuance and edge PUT

Authenticated `POST /api/netrapi/s3-upload-url` (JSON, no file) returns a
PUT URL. The client PUTs bytes to that URL with no AWS keys. The object
exists at the assigned key; SQLite `s3_stored` stays null until TP-47.

Needs AWS in gitignored `src/main/backend/.env` (same as TP-38).

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_43\tp_43_s3_upload_url.py
```
