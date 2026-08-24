# NetraPi frontend

Vite + React + TypeScript + Tailwind static app. Event list, playback, and
metrics are not wired yet. The FastAPI ingest API on Render is not called from
this package.

There is no committed `.env` example (decision 45). When a backend URL is
needed, document the `VITE_*` keys here and keep the file gitignored.

## Run locally

From `src/main/frontend` (Node.js required):

```bat
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`). Other scripts:

```bat
npm test
npm run build
npm run preview
```

## Vercel (later)

Do not create the Vercel project in this scaffold pass.

When connecting the repo, set **Root Directory** to `src/main/frontend`.
Build is `npm run build`; output is `dist`. `vercel.json` rewrites unknown
paths to `index.html` for the SPA.
