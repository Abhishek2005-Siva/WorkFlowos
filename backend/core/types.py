"""Shared enums and lightweight in-memory types used across the backend."""
from __future__ import annotations

from enum import StrEnum


class AgentStatus(StrEnum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    NEGOTIATING = "negotiating"
    WAITING = "waiting"
    ESCALATED = "escalated"
    ERROR = "error"


class EventType(StrEnum):
    EMAIL_RECEIVED = "email_received"
    AGENT_STATUS = "agent_status"
    AGENT_REASONING = "agent_reasoning"
    API_CALL = "api_call"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    CONFLICT_DETECTED = "conflict_detected"
    NEGOTIATION_STARTED = "negotiation_started"
    NEGOTIATION_PROPOSAL = "negotiation_proposal"
    NEGOTIATION_RESOLVED = "negotiation_resolved"
    TASK_CREATED = "task_created"
    EVENT_CREATED = "event_created"
    KB_LOGGED = "kb_logged"
    SLACK_NOTIFICATION = "slack_notification"
    WORKFLOW_COMPLETE = "workflow_complete"
    ERROR = "error"


class NegotiationState(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COUNTER_PROPOSED = "counter_proposed"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class IntentType(StrEnum):
    SCHEDULE_MEETING = "schedule_meeting"
    CREATE_TASK = "create_task"
    INFORM = "inform"
    URGENCY_FLAG = "urgency_flag"
