# TP-50 — Backend Docker image build

Builds the production `src/main/backend/Dockerfile` (same image Render
uses), runs one container, `GET /health`. Local boot uses sqlite + a dummy
`NETRAPI_API_KEY` so this does not need Render/Supabase env. `/` has no
route (404); health is `/health`.

**Prereq:** Docker Desktop running.

```bat
python src\tests\integration\tp_50\tp_50_backend_docker_image.py
```

The script removes the container when it finishes and leaves the image
tagged `netrapi-backend:tp50`.
