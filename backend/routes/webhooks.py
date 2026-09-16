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
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.core.approvals import approval_store
from backend.core.event_bus import event_bus
from backend.core.orchestrator import orchestrator
from backend.core.system_state import system_state
from backend.core.types import EventType
from backend.utils.logging import get_logger
from backend.utils.webhooks import verify_github_signature, verify_slack_signature

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
        # Pub/Sub firing correctly but silently doing nothing while
        # Stopped looks identical to Pub/Sub being broken — surface it on
        # the dashboard instead of only in backend logs nobody's watching.
        await event_bus.publish(
            type=EventType.EMAIL_RECEIVED,
            agent_name="System",
            message="📧 New email arrived — ignored because automation is Stopped. Click Go Live to process it.",
            category="warning",
        )
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
        return JSONResponse(status_code=401, content={"error": "invalid signature"})

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
    logger.info("webhook.todoist", event_name=payload.get("event_name"))
    return {"status": "accepted"}


async def _handle_pull_request(payload: dict) -> None:
    pr = payload["pull_request"]
    await orchestrator.pr_review_agent.review(
        pr_number=pr["number"],
        title=pr["title"],
        author=pr["user"]["login"],
        html_url=pr["html_url"],
    )


async def _handle_issue(payload: dict) -> None:
    issue = payload["issue"]
    await orchestrator.issue_triage_agent.triage(
        issue_number=issue["number"],
        title=issue["title"],
        body=issue.get("body") or "",
        html_url=issue["html_url"],
    )


@router.post("/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Backs PR Review (#3) and Issue Triage (#10). Registered via
    scripts/github_webhook_setup.py, which sets GITHUB_WEBHOOK_SECRET as
    the shared HMAC secret GitHub signs every payload with."""
    settings = get_settings()
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_github_signature(body, signature, settings.github_webhook_secret):
        logger.warning("webhook.github_invalid_signature")
        return {"status": "rejected"}

    event = request.headers.get("X-GitHub-Event", "")
    payload = json.loads(body)
    action = payload.get("action")

    if event == "pull_request" and action in ("opened", "reopened", "synchronize"):
        background_tasks.add_task(_handle_pull_request, payload)
    elif event == "issues" and action == "opened":
        background_tasks.add_task(_handle_issue, payload)
    else:
        logger.info("webhook.github_ignored", github_event=event, action=action)

    return {"status": "accepted"}
