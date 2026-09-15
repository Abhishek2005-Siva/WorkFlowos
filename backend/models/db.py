"""Async SQLAlchemy engine/session setup. Works with SQLite (default, zero
setup) or Postgres (set DATABASE_URL) transparently."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(32), default="default")
    agent_name: Mapped[str] = mapped_column(String(64), default="System")
    message: Mapped[str] = mapped_column(String(2000), default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class DecisionTrace(Base):
    __tablename__ = "decision_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    agent: Mapped[str] = mapped_column(String(64))
    decision_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(500))
    reasoning_trace: Mapped[list] = mapped_column(JSON, default=list)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    notion_page_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ConflictRecord(Base):
    __tablename__ = "conflict_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conflict_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    agent1: Mapped[str] = mapped_column(String(64))
    agent2: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(1000))
    negotiation_log: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    resolution: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class KnowledgeEntity(Base):
    """Lightweight local mirror of the Notion knowledge graph, so the graph
    visualization and pattern learning work even before/without Notion."""

    __tablename__ = "knowledge_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(32))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeRelationship(Base):
    __tablename__ = "knowledge_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_entity_id: Mapped[str] = mapped_column(String(128), index=True)
    to_entity_id: Mapped[str] = mapped_column(String(128), index=True)
    relationship_type: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetricRecord(Base):
    """Rolling performance metrics per agent execution, for the dashboard's
    performance panel and SLA warnings."""

    __tablename__ = "metric_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    operation: Mapped[str] = mapped_column(String(64))
    duration_seconds: Mapped[float] = mapped_column(Float)
    success: Mapped[bool] = mapped_column(default=True)


class ProcessedEmail(Base):
    """Idempotency guard for the Email Agent. Gmail push notifications
    fire on any mailbox change, not just new mail, and the agent always
    queries is:unread fresh — without this, the same still-unread email
    could get reprocessed (and re-approved into a duplicate real calendar
    invite) on every subsequent notification."""

    __tablename__ = "processed_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_async_engine(settings.database_url, echo=False, connect_args=connect_args)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    async with get_session_factory()() as session:
        yield session
