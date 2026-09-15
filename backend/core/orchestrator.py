"""Central orchestrator: a LangGraph state machine that routes each
actionable email intent through approval, scheduling, conflict
negotiation, task creation, knowledge-graph logging, and notification.

One graph invocation handles one actionable item extracted from an email.
`run_cycle()` fetches unread mail, then runs the graph once per action
found, so a batch of 3 emails becomes 3 independent, fully-traced
workflow runs.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.alert_agent import AlertAgent
from backend.config import get_settings
from backend.agents.calendar_agent import CalendarAgent
from backend.agents.email_agent import EmailAgent
from backend.agents.github_agent import GitHubAgent
from backend.agents.knowledge_graph_agent import KnowledgeGraphAgent
from backend.agents.slack_agent import SlackAgent
from backend.agents.task_agent import TaskAgent
from backend.core.approvals import approval_store
from backend.core.event_bus import event_bus, new_id
from backend.core.protocol import AgentNegotiationProtocol
from backend.core.types import EventType
from backend.utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowState(TypedDict, total=False):
    action: dict[str, Any]
    decision_id: str
    approved: bool
    duration_minutes: int
    slots: list[dict[str, Any]]
    chosen_slot: dict[str, Any]
    conflict_task: dict[str, Any] | None
    negotiation_result: dict[str, Any] | None
    calendar_event: dict[str, Any]
    task_result: dict[str, Any]
    summary: str
    skip_kb: bool
    learned_pattern: str | None


def _extract_email(header_value: str) -> str:
    match = re.search(r"<([^>]+)>", header_value)
    if match:
        return match.group(1)
    return header_value.strip()


class Orchestrator:
    def __init__(self) -> None:
        self.email_agent = EmailAgent()
        self.calendar_agent = CalendarAgent()
        self.task_agent = TaskAgent()
        self.knowledge_graph_agent = KnowledgeGraphAgent()
        self.slack_agent = SlackAgent()
        self.alert_agent = AlertAgent()
        self.github_agent = GitHubAgent()
        self.protocol = AgentNegotiationProtocol(self.calendar_agent, self.task_agent)

        self.agents = {
            "email": self.email_agent,
            "calendar": self.calendar_agent,
            "task": self.task_agent,
            "knowledge_graph": self.knowledge_graph_agent,
            "slack": self.slack_agent,
            "alert": self.alert_agent,
            "github": self.github_agent,
        }

        self.graph = self._build_graph()
        self.completed_workflows: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Graph construction
    # ------------------------------------------------------------------ #
    def _build_graph(self):
        graph = StateGraph(WorkflowState)

        graph.add_node("request_approval", self._node_request_approval)
        graph.add_node("calendar_check", self._node_calendar_check)
        graph.add_node("task_conflict_check", self._node_task_conflict_check)
        graph.add_node("negotiate", self._node_negotiate)
        graph.add_node("create_event", self._node_create_event)
        graph.add_node("create_prep_tasks", self._node_create_prep_tasks)
        graph.add_node("create_task_only", self._node_create_task_only)
        graph.add_node("handle_other", self._node_handle_other)
        graph.add_node("log_and_notify", self._node_log_and_notify)

        graph.add_conditional_edges(
            START,
            self._route_intent,
            {
                "schedule_meeting": "request_approval",
                "create_task": "request_approval",
                "urgency_flag": "handle_other",
                "inform": "handle_other",
            },
        )

        graph.add_conditional_edges(
            "request_approval",
            self._route_after_approval,
            {
                "approved_meeting": "calendar_check",
                "approved_task": "create_task_only",
                "rejected": "log_and_notify",
            },
        )

        graph.add_edge("calendar_check", "task_conflict_check")

        graph.add_conditional_edges(
            "task_conflict_check",
            lambda s: "conflict" if s.get("conflict_task") else "no_conflict",
            {"conflict": "negotiate", "no_conflict": "create_event"},
        )

        graph.add_conditional_edges(
            "negotiate",
            lambda s: (s.get("negotiation_result") or {}).get("status") == "resolved" and "resolved" or "escalated",
            {"resolved": "create_event", "escalated": "log_and_notify"},
        )

        graph.add_edge("create_event", "create_prep_tasks")
        graph.add_edge("create_prep_tasks", "log_and_notify")
        graph.add_edge("create_task_only", "log_and_notify")
        graph.add_edge("handle_other", "log_and_notify")
        graph.add_edge("log_and_notify", END)

        return graph.compile()

    # ------------------------------------------------------------------ #
    # Routing functions
    # ------------------------------------------------------------------ #
    def _route_intent(self, state: WorkflowState) -> str:
        return state["action"]["intent"]["action"]

    def _route_after_approval(self, state: WorkflowState) -> str:
        if not state.get("approved"):
            return "rejected"
        intent_action = state["action"]["intent"]["action"]
        return "approved_meeting" if intent_action == "schedule_meeting" else "approved_task"

    # ------------------------------------------------------------------ #
    # Node implementations
    # ------------------------------------------------------------------ #
    async def _node_request_approval(self, state: WorkflowState) -> dict[str, Any]:
        action = state["action"]
        intent = action["intent"]
        decision_id = new_id("decision")

        if intent["action"] == "schedule_meeting":
            title = f"Schedule meeting: {intent['topic']}"
            description = (
                f"{intent['requester']} wants to sync on \"{intent['topic']}\" "
                f"(~{intent.get('duration_estimated') or 30}min, {intent['urgency']} priority)."
            )
        else:
            title = f"Create task: {intent['topic']}"
            description = f"Requested by {intent['requester']}: {intent['context']}"

        await self.slack_agent.post_decision_for_approval(decision_id, action.get("from", "Email Agent"), title, description)
        approved = await approval_store.wait_for(decision_id, timeout=get_settings().approval_timeout_seconds)

        return {"decision_id": decision_id, "approved": approved}

    async def _node_calendar_check(self, state: WorkflowState) -> dict[str, Any]:
        intent = state["action"]["intent"]
        duration = intent.get("duration_estimated") or 30
        slots = await self.calendar_agent.check_availability(duration)

        if not slots:
            return {"duration_minutes": duration, "slots": [], "chosen_slot": None}

        return {"duration_minutes": duration, "slots": slots, "chosen_slot": slots[0]}

    async def _node_task_conflict_check(self, state: WorkflowState) -> dict[str, Any]:
        slot = state.get("chosen_slot")
        if not slot:
            return {"conflict_task": None}

        conflict = await self.task_agent.check_deadline_conflicts(
            datetime.fromisoformat(slot["start"]), datetime.fromisoformat(slot["end"])
        )
        return {"conflict_task": conflict}

    async def _node_negotiate(self, state: WorkflowState) -> dict[str, Any]:
        result = await self.protocol.negotiate_meeting_conflict(
            state["chosen_slot"], state["duration_minutes"], state["conflict_task"]
        )
        updated_slot = result["final_slot"] or state["chosen_slot"]
        return {"negotiation_result": result, "chosen_slot": updated_slot}

    async def _node_create_event(self, state: WorkflowState) -> dict[str, Any]:
        action = state["action"]
        intent = action["intent"]
        slot = state["chosen_slot"]

        attendee = _extract_email(action.get("from", ""))
        event_data = {
            "title": f"{intent['topic']} - {intent['requester']}",
            "description": intent.get("context", ""),
            "start_time": slot["start"],
            "end_time": slot["end"],
            "attendees": [attendee] if attendee else [],
        }
        result = await self.calendar_agent.create_event(event_data)
        return {"calendar_event": {**result, **event_data}}

    async def _node_create_prep_tasks(self, state: WorkflowState) -> dict[str, Any]:
        intent = state["action"]["intent"]
        meeting_start = datetime.fromisoformat(state["chosen_slot"]["start"])

        action = {
            "title": f"{intent['topic']} — meeting prep",
            "description": f"Prep for meeting with {intent['requester']}",
            "subtasks": [
                {
                    "title": f"Prepare {intent['topic']} doc",
                    "deadline": (meeting_start - timedelta(hours=21)).isoformat(),
                },
                {
                    "title": f"Review {intent['requester']}'s previous notes",
                    "deadline": (meeting_start - timedelta(hours=22)).isoformat(),
                },
                {
                    "title": f"Send agenda to {intent['requester']}",
                    "deadline": (meeting_start - timedelta(minutes=30)).isoformat(),
                },
            ],
        }
        result = await self.task_agent.create_task_hierarchy(action)
        return {"task_result": result}

    async def _node_create_task_only(self, state: WorkflowState) -> dict[str, Any]:
        intent = state["action"]["intent"]
        action = {"title": intent["topic"], "description": intent.get("context", "")}
        result = await self.task_agent.create_task_hierarchy(action)
        return {"task_result": result}

    async def _node_handle_other(self, state: WorkflowState) -> dict[str, Any]:
        action = state["action"]
        intent = action["intent"]

        if intent["action"] == "urgency_flag":
            await self.alert_agent.send_alert(f"🚨 Urgent: {intent['topic']} (from {intent['requester']})")
            if any(k in intent["topic"].lower() for k in ["error", "bug", "production", "outage", "down"]):
                await self.github_agent.file_bug(
                    title=intent["topic"],
                    body=f"Auto-filed from email by {intent['requester']}.\n\nContext: {intent['context']}",
                    severity="high",
                )
            summary = f"🚨 Urgent item flagged and routed: {intent['topic']}"
        else:
            summary = f"ℹ️ Informational email logged: {intent['topic']}"

        await self.slack_agent.post_agent_message("Slack Coordination Hub", summary)
        return {"summary": summary, "skip_kb": False}

    async def _node_log_and_notify(self, state: WorkflowState) -> dict[str, Any]:
        action = state["action"]
        intent = action["intent"]

        if not state.get("approved", True) and intent["action"] in ("schedule_meeting", "create_task"):
            summary = f"❌ Rejected by human: {intent['topic']}"
            await self.slack_agent.notify_completion(summary)
            return {"summary": summary}

        negotiation = state.get("negotiation_result")
        if negotiation and negotiation["status"] != "resolved":
            summary = f"🚨 Escalated to human review: could not schedule \"{intent['topic']}\" automatically"
            await self.slack_agent.notify_completion(summary)
            return {"summary": summary}

        if state.get("summary"):
            # handle_other already built + sent its own summary/notification
            decision_data = {
                "agent": "System",
                "type": intent["action"],
                "title": intent["topic"],
                "reasoning_trace": [],
                "person": intent.get("requester"),
            }
            await self.knowledge_graph_agent.log_decision(decision_data)
            return {}

        if intent["action"] == "schedule_meeting":
            slot = state["chosen_slot"]
            event = state["calendar_event"]
            subtasks = [t["content"] for t in state["task_result"]["subtasks"]]

            decision_data = {
                "agent": "System",
                "type": "meeting_scheduled",
                "title": event["title"],
                "person": intent["requester"],
                "event": event["title"],
                "reasoning_trace": (
                    self.calendar_agent.reasoning_trace[-5:] + self.task_agent.reasoning_trace[-5:]
                ),
                "final_time_scheduled": slot["start"],
                "conflicts_detected": 1 if negotiation else 0,
                "resolution_path": "agent_negotiated" if negotiation else "no_conflict",
                "google_meet_link": event.get("meet_link"),
                "related_tasks": subtasks,
            }
            await self.knowledge_graph_agent.log_decision(decision_data)
            learned = await self.knowledge_graph_agent.learn_pattern(intent["requester"])

            summary_lines = [
                f"✅ Meeting scheduled! 📅 {slot['start']} with {intent['requester']}",
                f"📝 {event['title']}",
                f"🔗 Meet: {event.get('meet_link')}",
            ]
            if negotiation:
                summary_lines.append(
                    f"⚠️ Note: original time conflicted with a task deadline — agents negotiated → {slot['start']}"
                )
            summary_lines.append(f"📋 {len(subtasks)} prep tasks created")
            if learned:
                summary_lines.append(f"🧠 Learned: {learned}")

            summary = "\n".join(summary_lines)
            await self.slack_agent.notify_completion(summary)
            return {"summary": summary, "learned_pattern": learned}

        # create_task path
        task_result = state["task_result"]
        decision_data = {
            "agent": "System",
            "type": "task_created",
            "title": task_result["main_task"]["content"],
            "person": intent.get("requester"),
            "reasoning_trace": self.task_agent.reasoning_trace[-5:],
        }
        await self.knowledge_graph_agent.log_decision(decision_data)

        summary = f"✅ Task created: {task_result['main_task']['content']} (requested by {intent['requester']})"
        await self.slack_agent.notify_completion(summary)
        return {"summary": summary}

    # ------------------------------------------------------------------ #
    # Entry points
    # ------------------------------------------------------------------ #
    async def run_action(self, action: dict[str, Any]) -> dict[str, Any]:
        initial_state: WorkflowState = {"action": action}
        final_state = await self.graph.ainvoke(initial_state)
        record = {
            "action": action,
            "summary": final_state.get("summary", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.completed_workflows.append(record)
        await event_bus.publish(
            type=EventType.WORKFLOW_COMPLETE,
            agent_name="System",
            message=final_state.get("summary", "Workflow complete"),
            data={"action": action},
            category="success",
        )
        return final_state

    async def seed_demo_conflict(self) -> dict[str, Any]:
        """Guarantees the flagship "agents negotiate a conflict" scenario
        fires on the next cycle, regardless of what time it is: reset the
        mock inbox to the scheduling email, find the Calendar Agent's top
        slot, then seed a Todoist deadline that lands exactly on it."""
        self.email_agent.gmail_client.reset_mock_cursor()
        slots = await self.calendar_agent.check_availability(30)
        if not slots:
            return {"seeded": False}

        top_start = datetime.fromisoformat(slots[0]["start"])
        task = await self.task_agent.seed_mock_deadline("Quarterly planning doc", top_start)
        return {"seeded": True, "task": task, "top_slot": slots[0]}

    async def run_cycle(self, max_emails: int = 3) -> list[dict[str, Any]]:
        """Fetch unread email, extract actions, run one workflow per
        action. This is what a Gmail push-notification webhook (or, for
        now, a periodic poller) triggers."""
        email_result = await self.email_agent.execute({"max_results": max_emails})
        results = []
        for action in email_result["actions"]:
            try:
                final_state = await self.run_action(action)
                results.append(final_state)
            except Exception as exc:
                logger.error("orchestrator.run_action_failed", error=str(exc))
                await event_bus.publish(
                    type=EventType.ERROR,
                    agent_name="System",
                    message=f"Workflow failed for \"{action['subject']}\": {exc}",
                    category="error",
                )
        return results

    def get_agents_status(self) -> list[dict[str, Any]]:
        return [agent.to_status_dict() for agent in self.agents.values()]


orchestrator = Orchestrator()
