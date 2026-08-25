# NetraPi frontend

Vite + React + TypeScript + Tailwind static app. Try it out mints a short-lived
S3 GET URL from FastAPI (`POST /api/public/clip-download-url`). Do **not** put
`NETRAPI_API_KEY` (or AWS keys) in any `VITE_*` variable — the built JS is public.

There is no committed `.env` example (decision 45). When the SPA is not served
from the same origin as FastAPI, set `VITE_API_URL` to the Render origin (no
trailing slash), e.g. `https://netrapi.onrender.com`. Local `npm run dev` leaves
it unset and Vite proxies `/api` to `http://127.0.0.1:8000`.

## Run locally

From `src/main/frontend` (Node.js required):

```bat
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). Start FastAPI on
port 8000 for live clip list + playback. Other scripts:

```bat
npm test
npm run build
npm run preview
```

## Vercel (later)

When connecting the repo, set **Root Directory** to `src/main/frontend`.
Build is `npm run build`; output is `dist`. `vercel.json` rewrites unknown
paths to `index.html` for the SPA. Set `VITE_API_URL` to the Render backend.
On Render, add that Vercel origin to `CORS_ORIGINS`.
