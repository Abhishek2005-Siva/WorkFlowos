# 🤖 WorkflowOS

**Live:** https://workflowos-alpha.vercel.app (frontend) ·
https://backend-production-e622.up.railway.app (backend API) — running in
real mode with NVIDIA, Todoist, Notion, GitHub, Telegram, and Discord
connected. Gmail/Calendar and Slack are still pending on your end (Google
OAuth consent + Slack channel creation — see
[docs/API_INTEGRATIONS.md](docs/API_INTEGRATIONS.md)).

Multi-agent orchestration platform: an Email Agent extracts intent with
an LLM (NVIDIA NIM), a Calendar Agent finds a slot, a Task Agent flags a deadline
conflict, and the two **negotiate a new time with each other** — no human
in the loop — before a Knowledge Graph Agent logs the whole reasoning
trace and a Slack hub notifies the team.

It runs fully in **mock mode** today (zero API keys needed) so the entire
pipeline — orchestration, negotiation, knowledge graph, live dashboard —
is buildable and testable before any real credentials exist. See
[docs/API_INTEGRATIONS.md](docs/API_INTEGRATIONS.md) for turning on real
Gmail/Slack/Notion/etc. one at a time.

For how it's wired together, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Quick start

### Backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

cp .env.example .env          # defaults to MOCK_MODE=true, SQLite, local Redis

python -m uvicorn backend.main:app --reload --port 8000
```

Postgres and Redis are optional — SQLite is the default `DATABASE_URL`,
and the cache silently falls back to an in-process dict if Redis isn't
running. If you do have them (`sudo systemctl status postgresql redis`),
nothing extra is needed — just point `DATABASE_URL` / `REDIS_URL` in
`.env` at them.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Click **"Run Negotiation Demo"** — this
seeds a task deadline that collides with the Calendar Agent's top slot,
then processes the mock "Quick sync on Q4 strategy" email, so you watch
the Calendar and Task agents negotiate a new time live in the Conflicts
panel and event stream. **"Process Inbox"** runs the whole mock inbox
(a meeting request, a task request, and an urgent/error email) through
the graph instead.

### CLI (no server needed)

```bash
python scripts/simulate_workflow.py            # negotiation demo, printed to terminal
python scripts/simulate_workflow.py --inbox    # process the full mock inbox
```

### Tests

```bash
python -m pytest tests/ -v
```

17 tests cover each agent in isolation, the negotiation protocol
(including a forced-escalation case), the knowledge graph's relationship
building and pattern learning, and three full orchestrator workflows
(meeting-with-conflict, plain task, urgency-flag).

---

## What's real vs. mocked right now

| Piece | Status |
|---|---|
| Orchestrator (LangGraph), negotiation protocol, event bus, approvals, base agent + fallback/retry | **Fully implemented, real logic** — nothing here is mocked, only its *inputs* are |
| Email/Calendar/Task/KnowledgeGraph/Slack agents | **Fully implemented** — real code paths, exercised via mock integration clients until you add keys |
| Gmail, Calendar, Slack, Todoist, Notion clients | Real API wrappers exist in `backend/integrations/`; return synthetic data while `MOCK_MODE=true` or their key is unset |
| GitHub, Google Sheets, Telegram, Discord (bonus agents) | Same pattern, lighter-weight, wired into the urgency-flag path (GitHub) and available standalone |
| Knowledge graph (local mirror) | Real SQLite/Postgres tables, populated on every decision — works with or without Notion configured |
| Dashboard | Live WebSocket feed, agent cards, conflict/negotiation viewer, decision timeline, hand-rolled SVG graph view |

Once you hand over API keys: fill in `.env` per
[docs/API_INTEGRATIONS.md](docs/API_INTEGRATIONS.md), set
`MOCK_MODE=false`, restart the backend, and re-run the same demo buttons
— the code path doesn't change, only where the data comes from.

---

## Project layout

```
backend/
  main.py                 FastAPI app, CORS, lifespan/startup
  config.py                Settings (pydantic-settings, reads .env)
  core/
    orchestrator.py        LangGraph state machine
    protocol.py             Calendar ↔ Task negotiation
    event_bus.py             asyncio pub/sub + DB persistence
    approvals.py             Slack-approval bridge (+ mock auto-approve)
    types.py                 Shared enums
  agents/                   One class per agent (all extend BaseAgent)
  integrations/             One thin API wrapper per external service
  models/db.py              SQLAlchemy async models (SQLite/Postgres)
  routes/                   agents, events, knowledge, webhooks, workflow, ws
  utils/                    llm.py (NVIDIA NIM), cache.py (Redis+fallback), logging, errors, webhooks

frontend/
  app/                      Next.js App Router (page.tsx, layout.tsx)
  components/               Dashboard, AgentCard, LiveEventStream, ConflictPanel,
                             DecisionTimeline, KnowledgeGraphView, ControlPanel, PerformanceMetrics
  hooks/                    useWebSocket, useWorkflowState
  lib/                      api-client.ts, types.ts

tests/                      pytest suite (async, mock-mode)
scripts/                    google_auth_setup.py, simulate_workflow.py
docs/                       ARCHITECTURE.md, API_INTEGRATIONS.md
```

---

## Next steps

1. Hand over the API keys you have — even one or two (Slack + Notion are
   the highest-impact pair) makes the demo materially more real.
2. I'll wire them into `.env`, flip `MOCK_MODE=false` for those services,
   and re-run the test suite + demo to catch anything a mock client
   didn't anticipate (real APIs are messier: rate limits, auth quirks,
   field-shape differences).
3. Iterate from there — this is meant to be a running conversation, not
   a one-shot handoff.
