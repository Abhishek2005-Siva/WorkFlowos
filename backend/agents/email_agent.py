"""Email Intake Agent — reads Gmail, uses Claude to extract actionable
intent (not keyword matching), and hands actions off for approval."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.exc import IntegrityError

from backend.agents.base_agent import BaseAgent
from backend.core.types import AgentStatus, EventType
from backend.core.event_bus import event_bus
from backend.integrations.gmail import GmailClient
from backend.models.db import ProcessedEmail, get_session_factory
from backend.utils.llm import llm_extract_intent

# Gmail's own "category:primary" already excludes Social/Promotions/Updates/
# Forums (which is where LinkedIn, most newsletters, and app notifications
# land), so this is a defense-in-depth pass for the cases that slip through
# — automated senders that still land in Primary.
_AUTOMATED_SENDER_PATTERN = re.compile(
    r"no-?reply|notifications?@|@(linkedin|facebook(?:mail)?|twitter|x|instagram|pinterest|quora)\.com",
    re.IGNORECASE,
)


def _is_automated_sender(from_header: str) -> bool:
    return bool(_AUTOMATED_SENDER_PATTERN.search(from_header))


class EmailAgent(BaseAgent):
    def __init__(self, gmail_client: GmailClient | None = None):
        super().__init__("Email Agent", "email_processor")
        self.gmail_client = gmail_client or GmailClient()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        await self.set_status(AgentStatus.THINKING)
        await self.log_reasoning("Fetching unread emails from Gmail", 1)

        messages = await self.run_with_fallback(
            "fetch_emails",
            lambda: self.gmail_client.list_messages(
                query="is:unread category:primary", max_results=context.get("max_results", 3)
            ),
            cache_key="last_email_batch",
        )

        await event_bus.publish(
            type=EventType.EMAIL_RECEIVED,
            agent_name=self.name,
            message=f"Found {len(messages)} unread email(s)",
            data={"count": len(messages)},
        )

        actions = []
        for message in messages:
            if _is_automated_sender(message["from"]):
                await self.log_reasoning(f"Skipping automated sender: {message['from']}")
                continue

            if not self.gmail_client.is_mock and not await self._claim_message(message["id"]):
                await self.log_reasoning(f"Skipping already-processed email: \"{message['subject']}\"")
                continue

            await self.log_reasoning(f"Analyzing email from {message['from']}: \"{message['subject']}\"")

            intent = await llm_extract_intent(
                {"subject": message["subject"], "from": message["from"], "body": message["body"]}
            )

            await self.log_reasoning(
                f"LLM extracted intent: {intent['action']} (confidence {intent.get('confidence', 0):.0%})"
            )

            actions.append(
                {
                    "email_id": message["id"],
                    "from": message["from"],
                    "subject": message["subject"],
                    "intent": intent,
                    "requires_approval": True,
                }
            )

        await self.set_status(AgentStatus.IDLE)
        return {
            "agent": self.name,
            "actions_found": len(actions),
            "actions": actions,
            "reasoning_trace": self.reasoning_trace,
        }

    async def _claim_message(self, message_id: str) -> bool:
        """Atomically claim a message ID for processing. Returns False if
        it was already claimed (by this call or a concurrent one) — the
        insert's unique constraint is what makes this race-safe, not the
        check itself."""
        async with get_session_factory()() as session:
            session.add(ProcessedEmail(message_id=message_id))
            try:
                await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                return False
