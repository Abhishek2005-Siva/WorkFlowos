#!/usr/bin/env python3
"""One-time (well — re-run every ~6 days, or let the backend auto-renew)
setup for real-time Gmail push notifications via Cloud Pub/Sub.

Prerequisite: run scripts/google_auth_setup.py first — this reuses that
same token, which now includes the pubsub scope.

    python scripts/gmail_watch_setup.py

What it does:
  1. Creates a Pub/Sub topic in your GCP project (idempotent — fine to
     re-run).
  2. Grants Gmail's push service account permission to publish to it.
  3. Creates (or updates) a push subscription pointing at your deployed
     backend's /webhooks/gmail endpoint.
  4. Calls Gmail's users.watch() to actually start the notifications.
  5. Prints the exact env vars to set (GMAIL_WATCH_TOPIC,
     GMAIL_WEBHOOK_SECRET) — set them in both .env and your Railway
     service, then redeploy. Once GMAIL_WATCH_TOPIC is set, the backend
     renews the watch automatically every ~6 days on its own; you only
     need to run this script again if you want to change the webhook URL
     or the secret.
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.config import get_settings
from backend.integrations.gmail import GmailClient

TOPIC_NAME = "gmail-notifications"
SUBSCRIPTION_NAME = "gmail-notifications-push"
GMAIL_PUSH_SERVICE_ACCOUNT = "serviceAccount:gmail-api-push@system.gserviceaccount.com"
DEFAULT_BACKEND_URL = "https://backend-production-e622.up.railway.app"


def _project_id(settings) -> str:
    with open(settings.google_credentials_path) as f:
        data = json.load(f)
    inner = data.get("installed") or data.get("web")
    return inner["project_id"]


def main() -> None:
    settings = get_settings()
    token_path = Path(settings.google_token_path)

    if not token_path.exists():
        print("❌ No token found — run scripts/google_auth_setup.py first.")
        sys.exit(1)

    project_id = _project_id(settings)
    topic_resource = f"projects/{project_id}/topics/{TOPIC_NAME}"
    subscription_resource = f"projects/{project_id}/subscriptions/{SUBSCRIPTION_NAME}"

    backend_url = input(f"Deployed backend URL [{DEFAULT_BACKEND_URL}]: ").strip() or DEFAULT_BACKEND_URL

    webhook_secret = settings.gmail_webhook_secret or secrets.token_urlsafe(24)
    webhook_url = f"{backend_url.rstrip('/')}/webhooks/gmail?token={webhook_secret}"

    creds = Credentials.from_authorized_user_file(str(token_path))
    pubsub = build("pubsub", "v1", credentials=creds)

    print(f"Project: {project_id}")

    # 1. Topic
    try:
        pubsub.projects().topics().create(name=topic_resource, body={}).execute()
        print(f"✅ Created topic {topic_resource}")
    except HttpError as e:
        if e.resp.status == 409:
            print(f"= Topic {topic_resource} already exists, reusing it")
        else:
            print(f"❌ Failed to create topic: {e}")
            print("   Make sure the Pub/Sub API is enabled: "
                  f"https://console.cloud.google.com/apis/library/pubsub.googleapis.com?project={project_id}")
            sys.exit(1)

    # 2. Grant Gmail permission to publish to it
    policy = pubsub.projects().topics().getIamPolicy(resource=topic_resource).execute()
    bindings = policy.get("bindings", [])
    publisher_binding = next((b for b in bindings if b["role"] == "roles/pubsub.publisher"), None)
    if publisher_binding is None:
        bindings.append({"role": "roles/pubsub.publisher", "members": [GMAIL_PUSH_SERVICE_ACCOUNT]})
    elif GMAIL_PUSH_SERVICE_ACCOUNT not in publisher_binding["members"]:
        publisher_binding["members"].append(GMAIL_PUSH_SERVICE_ACCOUNT)
    policy["bindings"] = bindings
    pubsub.projects().topics().setIamPolicy(resource=topic_resource, body={"policy": policy}).execute()
    print("✅ Granted Gmail's push service account publish rights")

    # 3. Push subscription
    sub_body = {"topic": topic_resource, "pushConfig": {"pushEndpoint": webhook_url}}
    try:
        pubsub.projects().subscriptions().create(name=subscription_resource, body=sub_body).execute()
        print(f"✅ Created subscription {subscription_resource} → {backend_url}/webhooks/gmail")
    except HttpError as e:
        if e.resp.status == 409:
            pubsub.projects().subscriptions().patch(
                subscriptionName=subscription_resource,
                body={"subscription": sub_body, "updateMask": "pushConfig"},
            ).execute()
            print(f"= Subscription already existed, updated its push endpoint to {backend_url}/webhooks/gmail")
        else:
            print(f"❌ Failed to create subscription: {e}")
            sys.exit(1)

    # 4. Start the watch
    import asyncio

    gmail = GmailClient()
    result = asyncio.run(gmail.start_watch(topic_resource))
    print(f"✅ Gmail watch active. historyId={result.get('historyId')} expiration={result.get('expiration')}")

    print("\n" + "=" * 60)
    print("Set these in BOTH your local .env and the Railway service, then redeploy:")
    print(f"  GMAIL_WATCH_TOPIC={topic_resource}")
    print(f"  GMAIL_WEBHOOK_SECRET={webhook_secret}")
    print("=" * 60)
    print("Once GMAIL_WATCH_TOPIC is set, the backend renews the watch")
    print("automatically every ~6 days — you won't need to run this again")
    print("unless you change the webhook URL or want a new secret.")


if __name__ == "__main__":
    main()
