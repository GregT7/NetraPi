# TP-47 — confirm-s3-upload links S3 object to metadata

After TP-43 (presigned PUT), authenticated `POST /api/netrapi/confirm-s3-upload`
sets `s3_key` / `s3_stored` on the clip row. JSON only; no file body.

Needs AWS in gitignored `src/main/backend/.env`.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_47\tp_47_confirm_s3_upload.py
```
