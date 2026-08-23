# TP-33 — Supabase Postgres connectivity

Admin path from the **development machine** (`test.md`): project exists, `SELECT 1`
works. This is **not** FastAPI (that is TP-39) and **not** the Pi (the Pi never
gets a cloud Postgres URL).

```bat
.\src\tests\integration\venv\Scripts\activate.bat
python src\tests\integration\tp_33\tp_33_supabase_postgres_connectivity.py
```

`psycopg2-binary==2.9.10` is installed by `src/create_env.bat` / `src/create_env.sh` (Python 3.9 wheels). Recreate the venv or `pip install psycopg2-binary==2.9.10` if this env was created before that pin.

The harness reads `DATABASE_URL` from gitignored `src/main/backend/.env`. It does not assemble a URI from `SUPABASE_DB_*`.

## Where to copy the value

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project.
2. **Project Settings** → **Database** → **Connect** → **Direct** (connection string).
3. Choose **Session pooler** and type **URI**.
4. Put that URI in `src/main/backend/.env` as:

```text
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres?sslmode=require
```

Use the SQLAlchemy driver prefix `postgresql+psycopg2://` (not `postgresql://` or `postgres://`). The password is the **database** password (Project Settings → Database), not your Supabase login. URL-encode special characters in the password.

Do not put this value on the Pi, in git, or in screenshots. `*.env` is gitignored; `.cursorignore` also excludes `.env`.
