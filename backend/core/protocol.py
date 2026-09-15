"""Agent-to-agent negotiation protocol.

This is the centerpiece of the system: when the Task Agent finds that the
Calendar Agent's proposed meeting time collides with a hard deadline, the
two agents negotiate directly — no human in the loop — until they reach
agreement or exhaust their iteration budget and escalate.

Flow per iteration:
  1. Calendar Agent proposes an alternative slot that avoids every slot
     rejected so far.
  2. Task Agent evaluates it against all known deadlines.
  3. Accept -> resolved. Reject -> the rejected slot is added to the avoid
     list and we loop. No alternative left, or max iterations reached ->
     escalate to a human via Slack.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.core.event_bus import event_bus, new_id
from backend.core.types import EventType, NegotiationState
from backend.models.db import ConflictRecord, get_session_factory

if TYPE_CHECKING:
    from backend.agents.calendar_agent import CalendarAgent
    from backend.agents.task_agent import TaskAgent


class AgentNegotiationProtocol:
    def __init__(
        self,
        calendar_agent: "CalendarAgent",
        task_agent: "TaskAgent",
        max_iterations: int = 5,
    ):
        self.calendar_agent = calendar_agent
        self.task_agent = task_agent
        self.max_iterations = max_iterations

    async def negotiate_meeting_conflict(
        self,
        original_slot: dict[str, Any],
        duration_minutes: int,
        conflicting_task: dict[str, Any],
    ) -> dict[str, Any]:
        conflict_id = new_id("conflict")
        negotiation_log: list[dict[str, Any]] = []
        avoid: list[tuple[datetime, datetime]] = [
            (datetime.fromisoformat(original_slot["start"]), datetime.fromisoformat(original_slot["end"]))
        ]

        description = (
            f"Proposed meeting at {original_slot['start']} conflicts with "
            f"deadline \"{conflicting_task['content']}\""
        )

        async with get_session_factory()() as session:
            session.add(
                ConflictRecord(
                    conflict_id=conflict_id,
                    agent1="Calendar Agent",
                    agent2="Task Agent",
                    description=description,
                    negotiation_log=[],
                    status=NegotiationState.PROPOSED.value,
                )
            )
            await session.commit()

        await event_bus.publish(
            type=EventType.CONFLICT_DETECTED,
            agent_name="Task Agent",
            message=f"⚠️ Conflict detected: {description}",
            data={"conflict_id": conflict_id, "agent1": "Calendar Agent", "agent2": "Task Agent"},
            category="conflict",
        )
        await event_bus.publish(
            type=EventType.NEGOTIATION_STARTED,
            agent_name="System",
            message="🤝 Negotiation started: Calendar Agent ↔ Task Agent",
            data={"conflict_id": conflict_id},
            category="negotiation",
        )

        state = NegotiationState.PROPOSED
        final_slot: dict[str, Any] | None = None

        for iteration in range(1, self.max_iterations + 1):
            alt_slot = await self.calendar_agent.propose_alternative(duration_minutes, avoid)

            if alt_slot is None:
                state = NegotiationState.ESCALATED
                negotiation_log.append(
                    {"iteration": iteration, "agent": "Calendar Agent", "proposal": "No alternative slots available"}
                )
                break

            proposal_msg = f"Counter-proposal: {alt_slot['start']} (score {alt_slot['score']})"
            negotiation_log.append({"iteration": iteration, "agent": "Calendar Agent", "proposal": proposal_msg})
            await event_bus.publish(
                type=EventType.NEGOTIATION_PROPOSAL,
                agent_name="Calendar Agent",
                message=f"💬 {proposal_msg}",
                data={"conflict_id": conflict_id, "slot": alt_slot},
                category="negotiation",
            )

            evaluation = await self.task_agent.evaluate_counter_proposal(
                datetime.fromisoformat(alt_slot["start"]), datetime.fromisoformat(alt_slot["end"])
            )

            eval_msg = (
                "Accepted — gives buffer time, no new conflicts"
                if evaluation["status"] == "accept"
                else f"Rejected — {evaluation.get('reason', 'still conflicts')}"
            )
            negotiation_log.append({"iteration": iteration, "agent": "Task Agent", "proposal": eval_msg})
            await event_bus.publish(
                type=EventType.NEGOTIATION_PROPOSAL,
                agent_name="Task Agent",
                message=f"💬 {eval_msg}",
                data={"conflict_id": conflict_id, "evaluation": evaluation},
                category="negotiation",
            )

            if evaluation["status"] == "accept":
                state = NegotiationState.RESOLVED
                final_slot = alt_slot
                break

            avoid.append((datetime.fromisoformat(alt_slot["start"]), datetime.fromisoformat(alt_slot["end"])))
            state = NegotiationState.COUNTER_PROPOSED
        else:
            state = NegotiationState.ESCALATED

        resolution = (
            f"Agreed on {final_slot['start']}" if final_slot else "No agreement reached — escalated to human review"
        )

        async with get_session_factory()() as session:
            result = await session.execute(select(ConflictRecord).where(ConflictRecord.conflict_id == conflict_id))
            record = result.scalar_one()
            record.negotiation_log = negotiation_log
            record.status = state.value
            record.resolution = resolution
            await session.commit()

        event_type = EventType.NEGOTIATION_RESOLVED if state == NegotiationState.RESOLVED else EventType.ERROR
        await event_bus.publish(
            type=event_type,
            agent_name="System",
            message=("✅ " if state == NegotiationState.RESOLVED else "🚨 ") + resolution,
            data={"conflict_id": conflict_id, "final_slot": final_slot, "status": state.value},
            category="conflict" if state != NegotiationState.RESOLVED else "success",
        )

        return {
            "status": state.value,
            "conflict_id": conflict_id,
            "final_slot": final_slot,
            "negotiation_log": negotiation_log,
            "resolution": resolution,
        }
