"""Inbound webhooks from external services.

Gmail's push notifications and Todoist's webhooks are stubbed to trigger a
workflow cycle — wiring the actual Cloud Pub/Sub subscription for Gmail is
a deployment-time concern (see docs/API_INTEGRATIONS.md) and isn't needed
for local development, where the poller in main.py drives the same code
path on an interval.
"""
from __future__ import annotations

import json
import urllib.parse

from fastapi import APIRouter, BackgroundTasks, Request

from backend.config import get_settings
from backend.core.approvals import approval_store
from backend.core.orchestrator import orchestrator
from backend.utils.logging import get_logger
from backend.utils.webhooks import verify_slack_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)


@router.post("/gmail")
async def gmail_webhook(background_tasks: BackgroundTasks):
    background_tasks.add_task(orchestrator.run_cycle)
    return {"status": "accepted"}


@router.post("/slack/interactivity")
async def slack_interactivity(request: Request):
    settings = get_settings()
    body = await request.body()

    signature = request.headers.get("X-Slack-Signature", "")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")

    if not verify_slack_signature(body, timestamp, signature, settings.slack_signing_secret):
        return {"error": "invalid signature"}, 401

    form = urllib.parse.parse_qs(body.decode())
    payload_raw = form.get("payload", ["{}"])[0]
    payload = json.loads(payload_raw)

    action = (payload.get("actions") or [{}])[0]
    action_id = action.get("action_id", "")
    decision_id = action.get("value", "")

    if action_id.startswith("approve_"):
        approval_store.resolve(decision_id, approved=True)
    elif action_id.startswith("reject_"):
        approval_store.resolve(decision_id, approved=False)

    return {"status": "ok"}


@router.post("/todoist")
async def todoist_webhook(request: Request):
    payload = await request.json()
    logger.info("webhook.todoist", event=payload.get("event_name"))
    return {"status": "accepted"}
