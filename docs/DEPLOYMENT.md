# Deployment

**Currently live:**
- Frontend (Vercel): https://workflowos-alpha.vercel.app — project
  `workflowos` under the `abhishek-kumars-projects-0c46e2ef` team.
- Backend (Railway): https://backend-production-e622.up.railway.app —
  project `workflowos`, service `backend`, environment `production`.
  Builds from `deployment/Dockerfile` on every push to `main`.

Both were set up via each platform's GraphQL/REST API directly (not the
CLIs — see "Why not the CLIs" below), using account API tokens. Below is
what was done, so you can reproduce it (a second environment, a different
service) or redo it if either project is ever deleted.

## Backend → Railway

1. Create a project, then a service with `source: { repo: "owner/repo" }`
   pointing at this GitHub repo (works for public repos with no GitHub
   App connection needed; private repos need Railway's GitHub App
   installed on the repo first — Project Settings → connect GitHub).
2. Configure the service instance: `dockerfilePath: "deployment/Dockerfile"`,
   `healthcheckPath: "/health"`. Leave `rootDirectory` unset — the
   Dockerfile's `COPY` paths are relative to the repo root.
3. Set every variable from `.env.example` (except the `NEXT_PUBLIC_*`
   frontend ones and the deploy tokens) via `variableCollectionUpsert`,
   plus `PORT=8000` matching the Dockerfile's exposed port.
4. `serviceDomainCreate` with `targetPort: 8000` to get a public
   `*.up.railway.app` domain.
5. `serviceInstanceDeploy` (or push to `main` — Railway auto-deploys on
   push once the repo source is connected) to build and deploy.
6. No Postgres/Redis plugin was provisioned — the backend runs on SQLite
   (fine for a single-instance demo; Railway's filesystem is ephemeral
   across deploys, so decision history resets on redeploy) and the cache
   falls back to an in-process dict when Redis isn't reachable. Add both
   plugins and set `DATABASE_URL`/`REDIS_URL` before this needs to
   survive redeploys or handle concurrent writers.

## Frontend → Vercel

1. `cd frontend && vercel link` (creates/links the project).
2. `vercel env add NEXT_PUBLIC_BACKEND_URL production` (the Railway
   domain, `https://`) and the same for `NEXT_PUBLIC_WS_URL` (`wss://`
   instead of `ws://`) — these are baked in at build time, so a value
   change always needs a redeploy, not just an env update.
3. `vercel deploy --prod`.

## Why not the CLIs

Both `railway` and `vercel` CLIs were tried first (via `npx`, since
global npm install wasn't permitted in this environment). Vercel's CLI
worked fine with `--token`. Railway's CLI rejected the account API token
for every command (`whoami`, `link`, `up` — all "Unauthorized"), even
though the exact same token worked for direct GraphQL calls to
`backboard.railway.com/graphql/v2` (queries and mutations both). The
CLI appears to gate every command behind a `me`-style identity check that
this token type doesn't satisfy, while the API itself doesn't require it
for project-scoped operations. If a future Railway CLI version fixes
this, `railway login --browserless` + `railway up` from the repo root is
the more standard path.

## CI

`.github/workflows/test.yml` runs the pytest suite and a frontend
production build on every push/PR. No auto-deploy step is wired up yet —
add a step that calls Railway's `serviceInstanceDeploy` mutation (or a
`vercel deploy --prod` for the frontend) once you're ready for push-to-deploy.

## Known gaps

- **Slack interactivity webhook** isn't configured — Slack's Approve/
  Reject buttons need `https://backend-production-e622.up.railway.app/webhooks/slack/interactivity`
  set as the Request URL under the Slack app's Interactivity settings.
  Until then, approvals only work through the dashboard's own
  Approve/Reject panel (`ApprovalPanel.tsx`), which is a complete
  functional substitute.
- **Google OAuth** hasn't been completed (`scripts/google_auth_setup.py`
  needs to run somewhere with a real browser + your Google login — not
  from this deployment). Gmail/Calendar/Sheets fall back to mock data
  until that token exists; nothing else in the pipeline is blocked by it.
- CORS is locked to `http://localhost:3000` plus a regex for
  `*.vercel.app` (see `backend/config.py: cors_origins` /
  `cors_origin_regex`) — update `CORS_ORIGINS` in Railway's variables if
  the frontend ever moves to a custom domain outside that pattern.
