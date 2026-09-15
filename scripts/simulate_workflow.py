#!/usr/bin/env python3
"""CLI demo runner — prints the full agent workflow to the terminal
without needing the dashboard or a running server. Good for a quick sanity
check after changing agent logic.

    python scripts/simulate_workflow.py            # runs the negotiation demo
    python scripts/simulate_workflow.py --inbox     # processes the whole mock inbox
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.event_bus import event_bus
from backend.core.orchestrator import Orchestrator
from backend.models.db import init_db


async def _print_events_as_they_happen():
    queue = await event_bus.subscribe()
    while True:
        event = await queue.get()
        print(f"[{event['type']:<22}] {event['agent_name']:<24} {event['message']}")


async def main() -> None:
    await init_db()
    orch = Orchestrator()

    printer = asyncio.create_task(_print_events_as_they_happen())

    if "--inbox" in sys.argv:
        print("=== Processing full mock inbox ===\n")
        await orch.run_cycle(max_emails=3)
    else:
        print("=== Running flagship negotiation demo ===\n")
        seed = await orch.seed_demo_conflict()
        print(f"(seeded conflicting deadline at {seed.get('top_slot', {}).get('start')})\n")
        await orch.run_cycle(max_emails=1)

    await asyncio.sleep(0.5)
    printer.cancel()

    print("\n=== Final summaries ===")
    for w in orch.completed_workflows:
        print(f"- {w['summary']}")


if __name__ == "__main__":
    asyncio.run(main())
