# TP-39 — Local backend can reach Supabase

Uses backend `app.config.Settings` to load `DATABASE_URL` from gitignored
`src/main/backend/.env` and run `SELECT 1`. No extra FastAPI route.
Compose `DATABASE_URL` (throwaway test Postgres, not prod) is not used.

This is the backend settings path. TP-33 is the same Postgres check without
`app.config`. The Pi never gets these credentials.

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_39\tp_39_local_backend_supabase.py
```

See `src/tests/integration/tp_33/README.md` for where to copy the Supabase URI.
