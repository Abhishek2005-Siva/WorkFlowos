# Deployment

Not deployed anywhere yet — this is what to do when you're ready.

## Backend → Railway

1. `railway login`, `railway init` from the repo root.
2. Railway picks up `deployment/railway.toml` (Dockerfile build).
3. Add a Postgres plugin (or keep SQLite by leaving `DATABASE_URL` unset
   — fine for a demo, not for anything with concurrent writers) and a
   Redis plugin.
4. Set every var from `.env.example` in Railway's dashboard, with
   `MOCK_MODE` and real keys as appropriate.
5. `railway up`.

## Frontend → Vercel

1. `cd frontend && vercel link && vercel deploy --prod`. Next.js needs no
   extra config — Vercel auto-detects it.
2. Set `NEXT_PUBLIC_BACKEND_URL` and `NEXT_PUBLIC_WS_URL` (use `wss://`,
   not `ws://`, once the backend is on HTTPS) in Vercel's project env
   vars to the deployed Railway URL.

## CI

`.github/workflows/test.yml` runs the pytest suite and a frontend
production build on every push/PR. No deploy step is wired up yet —
add one once the two steps above are done once manually and you know the
project/service names.

## Gotchas

- CORS in `backend/main.py` is currently wide open (`allow_origins=["*"]`)
  for local development. Lock it to the deployed frontend origin before
  calling this production-ready.
- The Slack interactivity webhook needs a public HTTPS URL — this is the
  one integration you can't fully test until the backend is deployed (or
  tunneled via `ngrok`).
