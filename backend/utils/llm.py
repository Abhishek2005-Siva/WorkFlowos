"""NVIDIA NIM (build.nvidia.com) LLM wrapper used for semantic understanding.

This is what separates the Email Agent from a keyword/regex automation:
`llm_extract_intent` reads a raw email and returns a structured, reasoned
judgement about what action (if any) it requires. NVIDIA's API is
OpenAI-compatible (same chat-completions request/response shape), called
directly via httpx to stay consistent with the rest of this codebase's
integration style rather than pulling in another SDK.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from backend.config import get_settings
from backend.utils.logging import get_logger

logger = get_logger(__name__)

NVIDIA_API_BASE = "https://integrate.api.nvidia.com/v1"

INTENT_SCHEMA_PROMPT = """You are the semantic reasoning core of an email intake agent in a \
multi-agent workflow automation system. Read the email below and extract the single most \
important actionable intent.

Respond with ONLY a JSON object (no markdown fences, no commentary) with exactly these keys:
{{
  "action": one of "schedule_meeting" | "create_task" | "inform" | "urgency_flag",
  "requester": the sender's display name,
  "topic": short topic summary (<= 8 words),
  "duration_estimated": integer minutes if action is schedule_meeting, else null,
  "urgency": one of "low" | "normal" | "high",
  "context": one sentence of context useful for scheduling/task creation,
  "confidence": float between 0 and 1
}}

Email:
Subject: {subject}
From: {sender}
Body:
{body}
"""


async def _chat_completion(prompt: str, max_tokens: int) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{NVIDIA_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.nvidia_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.nvidia_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        message = data["choices"][0]["message"]
        content = message.get("content")

        if not content:
            # Reasoning models (e.g. gpt-oss) can spend the whole token
            # budget "thinking" and hit max_tokens before emitting a final
            # answer, leaving content null with the work sitting in
            # reasoning_content instead. Surface *something* rather than
            # crash the caller with a None.strip() — that path is already
            # weaker output, so callers should still treat it as fallback-worthy.
            reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
            logger.warning(
                "llm.empty_content_using_reasoning_fallback",
                finish_reason=data["choices"][0].get("finish_reason"),
            )
            content = reasoning

        return content


def _heuristic_extract_intent(email: dict[str, Any]) -> dict[str, Any]:
    """Deterministic stand-in used in MOCK_MODE or when no API key is set,
    so the rest of the pipeline can be built/tested before the LLM is
    wired up. Not meant to compete with the real model's understanding."""
    subject = (email.get("subject") or "").lower()
    body = (email.get("body") or "").lower()
    text = f"{subject} {body}"

    sender = email.get("from", "Unknown")
    name_match = re.match(r"^([^<]+)", sender)
    requester = name_match.group(1).strip() if name_match else sender

    if any(k in text for k in ["sync", "meeting", "call", "schedule", "chat about", "catch up"]):
        action = "schedule_meeting"
        duration = 30
    elif any(k in text for k in ["please do", "can you", "action item", "todo", "task", "follow up"]):
        action = "create_task"
        duration = None
    elif any(k in text for k in ["urgent", "asap", "immediately", "critical"]):
        action = "urgency_flag"
        duration = None
    else:
        action = "inform"
        duration = None

    urgency = "high" if any(k in text for k in ["urgent", "asap", "immediately"]) else "normal"

    return {
        "action": action,
        "requester": requester,
        "topic": (email.get("subject") or "General topic")[:80],
        "duration_estimated": duration,
        "urgency": urgency,
        "context": f"Heuristic extraction (mock mode) from subject: {email.get('subject', '')}",
        "confidence": 0.6,
    }


async def llm_extract_intent(email: dict[str, Any]) -> dict[str, Any]:
    """Extract structured intent from an email. Falls back to a heuristic
    extractor in mock mode / when no API key is configured, so the pipeline
    is fully exercisable without spending on the LLM during development."""
    settings = get_settings()

    if settings.mock_mode or not settings.nvidia_api_key:
        return _heuristic_extract_intent(email)

    prompt = INTENT_SCHEMA_PROMPT.format(
        subject=email.get("subject", ""),
        sender=email.get("from", ""),
        body=(email.get("body", "") or "")[:4000],
    )

    try:
        raw_text = await _chat_completion(prompt, max_tokens=700)
        raw_text = raw_text.strip()
        raw_text = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
        # Despite the "respond with ONLY JSON" instruction, some models
        # still wrap it in a stray sentence — take the outermost {...}
        # block rather than assuming the whole trimmed string parses.
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if match:
            raw_text = match.group(0)
        return json.loads(raw_text)
    except Exception as exc:
        logger.error("llm.intent_extraction_failed", error=str(exc))
        fallback = _heuristic_extract_intent(email)
        fallback["context"] += " (LLM call failed, used heuristic fallback)"
        return fallback


async def llm_explain_slot_choice(slot: dict[str, Any], all_slots: list[dict[str, Any]]) -> str:
    """Generate a short natural-language reason for why a time slot was
    recommended (e.g. "high energy, post-lunch dip avoided"). Mocked with a
    rule-based explanation to avoid a network call for every slot."""
    settings = get_settings()
    if settings.mock_mode or not settings.nvidia_api_key:
        hour = slot.get("start_hour", 10)
        if 9 <= hour < 11:
            return "high energy morning slot, before meeting fatigue sets in"
        if 11 <= hour < 13:
            return "late morning, good focus window before lunch"
        if 13 <= hour < 15:
            return "early afternoon, post-lunch dip avoided"
        return "available slot within the requested window"

    try:
        prompt = (
            "In one short sentence (under 12 words), give a friendly scheduling reason for "
            f"picking this slot over alternatives: {slot}. Alternatives: {all_slots}. "
            "Respond with ONLY the sentence, no preamble."
        )
        # Reasoning models spend part of the budget "thinking" before the
        # final answer, so this needs real headroom despite the short
        # target output (see _chat_completion's reasoning_content fallback).
        text = await _chat_completion(prompt, max_tokens=300)
        return text.strip().strip('"')
    except Exception as exc:
        logger.warning("llm.slot_explanation_failed", error=str(exc))
        return "recommended based on availability"
