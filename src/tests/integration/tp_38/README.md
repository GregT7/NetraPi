# TP-38 — Local backend can reach S3

Uses backend `app.config.Settings` (gitignored `src/main/backend/.env`) to
PUT a tiny object under `_netrapi/tp-38/`, HEAD it, then delete it. No extra
FastAPI route. `/health` does not call S3.

Needs `DATABASE_URL` and `NETRAPI_API_KEY` in the same `.env` (Settings requires
them even though this script only uses AWS). Needs `boto3==1.35.99`:

```text
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-2
AWS_S3_BUCKET=netrapi-s3-bucket-820697996456-us-east-2-an
```

`AWS_ACCESS_KEY` is accepted as an alias of `AWS_ACCESS_KEY_ID`. Do not put
these values on the Pi.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_38\tp_38_local_backend_s3.py
```
