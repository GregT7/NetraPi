# TP-45 — driving-event persist to Supabase

Authenticated `POST /api/netrapi/driving-event` (JSON, no file) into
**Postgres** via backend `DATABASE_URL`. Cloud counterpart of TP-36.
Clip `s3_key` / `s3_stored` stay null until TP-47.

Needs gitignored `src/main/backend/.env` (`DATABASE_URL`, `NETRAPI_API_KEY`).
TP-39 / TP-40 / TP-42 should already pass. Row ids are in the 45_000_000
range so the upsert does not overwrite id 1 / 10.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_45\tp_45_driving_event_supabase.py
```
