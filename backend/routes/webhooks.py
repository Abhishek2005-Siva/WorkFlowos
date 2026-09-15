"""Inbound webhooks from external services.

Gmail's push notifications arrive here via a Cloud Pub/Sub push
subscription — see scripts/gmail_watch_setup.py for how that's wired up
(topic, IAM grant, subscription, and the users.watch() call that starts
it). Todoist's webhook is stubbed since nothing currently needs it.
"""
from __future__ import annotations

import base64
import json
import urllib.parse

from fastapi import APIRouter, BackgroundTasks, Request

from backend.config import get_settings
from backend.core.approvals import approval_store
from backend.core.orchestrator import orchestrator
from backend.core.system_state import system_state
from backend.utils.logging import get_logger
from backend.utils.webhooks import verify_slack_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)


@router.post("/gmail")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks, token: str = ""):
    """Pub/Sub push endpoint. Always acks with 200 quickly (Pub/Sub
    retries with backoff on anything else, which we don't want for a
    payload we simply couldn't parse) and does the actual work in the
    background.

    Auth: a shared secret in the URL (?token=...), matched against
    GMAIL_WEBHOOK_SECRET, since Pub/Sub push doesn't sign requests unless
    you configure OIDC auth on the subscription (a stronger option, not
    set up here — see docs/API_INTEGRATIONS.md).
    """
    settings = get_settings()
    if settings.gmail_webhook_secret and token != settings.gmail_webhook_secret:
        logger.warning("webhook.gmail_invalid_token")
        return {"status": "rejected"}

    if not system_state.is_live:
        logger.info("webhook.gmail_ignored_not_live")
        return {"status": "ignored", "reason": "not live"}

    try:
        envelope = await request.json()
        message = envelope.get("message", {})
        data_b64 = message.get("data", "")
        decoded = json.loads(base64.b64decode(data_b64).decode("utf-8")) if data_b64 else {}
        logger.info("webhook.gmail_notification", email=decoded.get("emailAddress"), history_id=decoded.get("historyId"))
    except Exception as exc:
        logger.warning("webhook.gmail_parse_failed", error=str(exc))

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
