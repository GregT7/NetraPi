# TP-49 — Local end-to-end event persistence via backend

Creates a local SQLite event + clip via `LocalStore`, then `CloudIngest`
(the same client the capture loop uses). Starts FastAPI against **Supabase**,
uploads session → event → presigned PUT → confirm. Then
`drain_trip_segments` PUTs the primed trip file (Wi‑Fi path). Inspects
Postgres and S3. After confirm, the **local** clip and trip rows also have
`s3_key` / `s3_stored` / `file_size_bytes`. Also upserts kNN /
approach / trip location and one `operational_exception`. Row ids are in
the 49_000_000 range so the upsert does not overwrite id 1.

Needs gitignored `src/main/backend/.env` (Supabase `DATABASE_URL`,
`NETRAPI_API_KEY`, AWS). TP-39/TP-40/TP-42/TP-43 should already pass.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_49\tp_49_local_event_backend_e2e.py
```
