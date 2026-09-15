# Architecture

This describes what's actually implemented, not the aspirational version.

## Layers

```
frontend/ (Next.js 16 + React 19, Tailwind 4)
    │  fetch + WebSocket
    ▼
backend/main.py (FastAPI)
    │  routes/*.py
    ▼
backend/core/orchestrator.py (LangGraph state machine)
    │
    ├── backend/agents/*.py        (one class per agent, all extend BaseAgent)
    ├── backend/core/protocol.py   (Calendar ↔ Task negotiation)
    ├── backend/core/event_bus.py  (in-process pub/sub → WebSocket + DB)
    └── backend/core/approvals.py  (Slack-approval / auto-approve bridge)
         │
         ▼
    backend/integrations/*.py (one wrapper per external API; each has a
    mock branch controlled by MOCK_MODE + presence of its own API key)
         │
         ▼
    backend/models/db.py (SQLAlchemy async ORM — SQLite by default,
    Postgres via DATABASE_URL; no separate migration files, schema is
    created via Base.metadata.create_all() at startup)
```

## Why LangGraph, and what the graph actually looks like

`Orchestrator._build_graph()` in `core/orchestrator.py` builds one
`StateGraph` that handles all four intent types the Email Agent can
extract. One graph invocation = one actionable email processed end to
end:

```
START ─┬─ schedule_meeting ─┐
       ├─ create_task ──────┼──► request_approval ─┬─ approved (meeting) ─► calendar_check ─► task_conflict_check ─┬─ no conflict ─► create_event ─► create_prep_tasks ─┐
       ├─ urgency_flag ─────┤                       ├─ approved (task) ────► create_task_only ───────────────────────────────────────────────────────────────────────┤
       └─ inform ───────────┤                       └─ rejected ─────────────────────────────────────────────────────────────────────────────────────────────────────┤
                             │                                                                                     └─ conflict ────► negotiate ─┬─ resolved ──► create_event (loop back up)
                             │                                                                                                                    └─ escalated ─────────────────────────────┤
                             └─► handle_other (urgency_flag / inform) ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
                                                                                                                                                                                                ▼
                                                                                                                                                                                          log_and_notify ──► END
```

Every node is a thin wrapper that calls into an agent method — the graph
owns *routing*, agents own *reasoning*. This split is what makes the
agents independently unit-testable (see `tests/test_calendar_agent.py`
etc. — none of them touch the graph).

## The negotiation protocol

`core/protocol.py: AgentNegotiationProtocol.negotiate_meeting_conflict()`
is the flagship "agents talk to each other" scenario:

1. Task Agent already found that the Calendar Agent's chosen slot
   collides with a deadline (`task_conflict_check` node).
2. Calendar Agent proposes the next-best slot that avoids everything
   rejected so far (`CalendarAgent.propose_alternative`).
3. Task Agent evaluates it against every known deadline
   (`TaskAgent.evaluate_counter_proposal`).
4. Accept → done. Reject → the slot joins the avoid-list, loop. Iteration
   budget exhausted or no slots left → escalate (surfaced in Slack + the
   dashboard's Conflicts panel, not silently dropped).

Every round is persisted to `ConflictRecord` and streamed through the
event bus, which is what the dashboard's "Conflicts & Negotiations" panel
and the CLI (`scripts/simulate_workflow.py`) both render live.

## Event bus, not a message queue

`core/event_bus.py` is a single in-process `asyncio.Queue`-per-subscriber
pub/sub, not Redis Streams or Kafka. That's a deliberate simplification:
this runs as one Uvicorn worker, so there's no cross-process fan-out to
justify a real broker. It still persists every event to `EventLog` so a
WebSocket reconnect (or `GET /events/recent`) replays history rather than
losing it. If this ever needs multiple workers, swap the queue fan-out
for a Redis pub/sub channel — the `publish()` call sites wouldn't change.

## Fallback strategy (where it lives)

`BaseAgent.run_with_fallback()` in `agents/base_agent.py` implements the
5-level fallback described in the original spec (immediate retry →
exponential backoff → cached data via `utils/cache.py` → escalate) as one
reusable wrapper, rather than duplicating retry logic in every agent.
Every external call an agent makes goes through it.

## Mock mode

Every integration client (`integrations/*.py`) checks
`settings.mock_mode or not settings.<service>_api_key` at the top of each
method and returns realistic synthetic data instead of calling out. This
is what let the whole system — orchestrator, negotiation, knowledge
graph, dashboard — get built and tested end to end before any real API
credentials existed. See `docs/API_INTEGRATIONS.md` for turning each one
on for real.

## Known simplifications (vs. the original spec)

- **No Alembic migrations** — schema is created via
  `Base.metadata.create_all()`. Fine for a single-environment project;
  would need real migrations before multiple environments diverge.
- **No Lottie animations** — the dashboard uses CSS transitions
  (pulse/ping on status dots) instead of the Lottie JSON files the
  original UI spec described. Simpler dependency footprint, same "alive"
  effect.
- **Knowledge graph visualization is hand-rolled SVG**, not D3
  force-simulation — concentric rings by entity type rather than a
  physics layout. Deterministic, no simulation-tick bugs, reads fine at
  the scale (dozens of nodes) this project produces.
- **Single Uvicorn worker** — see the event bus note above.
