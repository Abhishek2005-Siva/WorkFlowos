"""Knowledge Graph Agent.

Every decision any agent makes is logged here with its full reasoning
trace, and relationships are created between the people/meetings/tasks
involved. Notion is the source of truth when configured; a local SQLite/
Postgres mirror (KnowledgeEntity/KnowledgeRelationship) always exists too,
so the graph visualization and pattern learning ("Alex prefers mornings")
work instantly without waiting on Notion's rate limits.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from backend.agents.base_agent import BaseAgent
from backend.config import get_settings
from backend.core.event_bus import event_bus, new_id
from backend.core.types import AgentStatus, EventType
from backend.integrations.notion import NotionClient
from backend.models.db import DecisionTrace, KnowledgeEntity, KnowledgeRelationship, get_session_factory


class KnowledgeGraphAgent(BaseAgent):
    def __init__(self, notion_client: NotionClient | None = None):
        super().__init__("Knowledge Graph Agent", "memory_store")
        self.notion_client = notion_client or NotionClient()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        return await self.log_decision(context["decision_data"])

    async def log_decision(self, decision_data: dict[str, Any]) -> dict[str, Any]:
        await self.set_status(AgentStatus.ACTING)
        await self.log_reasoning("Creating decision record in knowledge graph")

        settings = get_settings()
        decision_id = new_id("decision")
        properties = self._build_notion_properties(decision_id, decision_data)

        page = await self.run_with_fallback(
            "create_decision_page",
            lambda: self.notion_client.create_page(
                settings.notion_decisions_db_id or "mock_decisions_db", properties
            ),
        )

        async with get_session_factory()() as session:
            session.add(
                DecisionTrace(
                    decision_id=decision_id,
                    agent=decision_data.get("agent", "orchestrator"),
                    decision_type=decision_data.get("type", "unknown"),
                    title=decision_data.get("title", "Untitled decision"),
                    reasoning_trace=decision_data.get("reasoning_trace", []),
                    data=decision_data,
                    notion_page_id=page.get("id"),
                )
            )
            await session.commit()

        await self.log_reasoning("Creating relationships to related entities")
        relationships = await self._upsert_relationships(decision_data)

        await event_bus.publish(
            type=EventType.KB_LOGGED,
            agent_name=self.name,
            message=f"📊 Logged decision \"{decision_data.get('title', decision_id)}\" ({len(relationships)} relationship(s))",
            data={"decision_id": decision_id, "notion_page_id": page.get("id"), "relationships": relationships},
        )

        await self.set_status(AgentStatus.IDLE)
        return {"decision_id": decision_id, "notion_page_id": page.get("id"), "relationships": relationships}

    def _build_notion_properties(self, decision_id: str, decision_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "Title": {"title": [{"text": {"content": decision_data.get("title", decision_id)}}]},
            "Agent": {"select": {"name": decision_data.get("agent", "orchestrator")}},
            "Decision Type": {"select": {"name": decision_data.get("type", "unknown")}},
            "Timestamp": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
            "Reasoning Trace": {
                "rich_text": [
                    {"text": {"content": json.dumps(decision_data.get("reasoning_trace", []))[:2000]}}
                ]
            },
        }

    async def _get_or_create_entity(
        self, session, name: str, entity_type: str, attributes: dict[str, Any] | None = None
    ) -> str:
        entity_id = f"{entity_type}:{name}".lower().replace(" ", "_")
        result = await session.execute(
            select(KnowledgeEntity).where(KnowledgeEntity.entity_id == entity_id)
        )
        row = result.scalars().first()
        if row is None:
            session.add(
                KnowledgeEntity(entity_id=entity_id, name=name, entity_type=entity_type, attributes=attributes or {})
            )
        return entity_id

    async def _link(self, session, from_id: str, to_id: str, rel_type: str) -> None:
        session.add(
            KnowledgeRelationship(from_entity_id=from_id, to_entity_id=to_id, relationship_type=rel_type)
        )

    async def _upsert_relationships(self, decision_data: dict[str, Any]) -> list[dict[str, str]]:
        relationships: list[dict[str, str]] = []

        async with get_session_factory()() as session:
            you_id = await self._get_or_create_entity(session, "You", "person")

            person_id = None
            if decision_data.get("person"):
                person_id = await self._get_or_create_entity(session, decision_data["person"], "person")
                await self._link(session, person_id, you_id, "has_meeting_with")
                relationships.append({"from": decision_data["person"], "to": "You", "type": "has_meeting_with"})

            meeting_id = None
            if decision_data.get("event"):
                meeting_id = await self._get_or_create_entity(
                    session,
                    decision_data["event"],
                    "meeting",
                    {
                        "final_time": decision_data.get("final_time_scheduled"),
                        "meet_link": decision_data.get("google_meet_link"),
                    },
                )
                if person_id:
                    await self._link(session, meeting_id, person_id, "attended_by")
                    relationships.append({"from": decision_data["event"], "to": decision_data["person"], "type": "attended_by"})

            for task_title in decision_data.get("related_tasks", []) or []:
                task_id = await self._get_or_create_entity(session, task_title, "task")
                if meeting_id:
                    await self._link(session, meeting_id, task_id, "requires_prep_of")
                    relationships.append({"from": decision_data["event"], "to": task_title, "type": "requires_prep_of"})

            if decision_data.get("conflicts_detected") and meeting_id:
                conflict_id = await self._get_or_create_entity(
                    session, f"deadline_conflict::{meeting_id}", "conflict"
                )
                await self._link(session, meeting_id, conflict_id, "had_conflict_resolved_via_negotiation")
                relationships.append(
                    {"from": decision_data["event"], "to": "conflict", "type": "had_conflict_resolved_via_negotiation"}
                )

            await session.commit()

        return relationships

    async def query_context(self, entity_name: str, entity_type: str) -> dict[str, Any]:
        entity_id = f"{entity_type}:{entity_name}".lower().replace(" ", "_")
        async with get_session_factory()() as session:
            result = await session.execute(
                select(KnowledgeRelationship).where(
                    (KnowledgeRelationship.from_entity_id == entity_id)
                    | (KnowledgeRelationship.to_entity_id == entity_id)
                )
            )
            rels = result.scalars().all()

        return {
            "entity": entity_name,
            "type": entity_type,
            "interactions": len(rels),
            "history": [
                {"from": r.from_entity_id, "to": r.to_entity_id, "type": r.relationship_type} for r in rels
            ],
        }

    async def learn_pattern(self, person: str) -> str | None:
        """Look at past meetings with this person and surface a simple
        learned preference, e.g. 'Alex prefers morning meetings'."""
        async with get_session_factory()() as session:
            result = await session.execute(
                select(KnowledgeEntity).where(KnowledgeEntity.entity_type == "meeting")
            )
            meetings = result.scalars().all()

        person_id = f"person:{person}".lower().replace(" ", "_")
        hours = []
        async with get_session_factory()() as session:
            for m in meetings:
                rel = await session.execute(
                    select(KnowledgeRelationship).where(
                        KnowledgeRelationship.from_entity_id == m.entity_id,
                        KnowledgeRelationship.to_entity_id == person_id,
                    )
                )
                if rel.scalars().first() and m.attributes.get("final_time"):
                    try:
                        hours.append(datetime.fromisoformat(m.attributes["final_time"]).hour)
                    except (ValueError, TypeError):
                        pass

        if len(hours) < 2:
            return None

        bucket = Counter("morning" if h < 12 else "afternoon" for h in hours)
        top, count = bucket.most_common(1)[0]
        if count / len(hours) >= 0.6:
            return f"{person} tends to have meetings scheduled in the {top} ({count}/{len(hours)} past meetings)"
        return None

    async def graph_snapshot(self) -> dict[str, Any]:
        async with get_session_factory()() as session:
            entities = (await session.execute(select(KnowledgeEntity))).scalars().all()
            relationships = (await session.execute(select(KnowledgeRelationship))).scalars().all()

        return {
            "entities": [
                {"id": e.entity_id, "name": e.name, "type": e.entity_type} for e in entities
            ],
            "relationships": [
                {"from_id": r.from_entity_id, "to_id": r.to_entity_id, "type": r.relationship_type}
                for r in relationships
            ],
        }
