#!/usr/bin/env python3
"""One-time setup for GitHub PR review (#3) and issue triage (#10):
registers a webhook on GITHUB_REPO pointed at the deployed backend's
/webhooks/github endpoint, fully via the GitHub REST API (no manual
dashboard step needed, unlike Slack/Discord).

    python scripts/github_webhook_setup.py

Prerequisites: GITHUB_TOKEN and GITHUB_REPO set in .env. The token needs
the "repo" scope (classic PAT) or "Webhooks: write" (fine-grained PAT).

What it does:
  1. Lists existing webhooks on the repo and skips creating a duplicate
     if one already points at the same backend URL.
  2. Generates a GITHUB_WEBHOOK_SECRET (if not already set) and creates
     the webhook subscribed to "pull_request" and "issues" events.
  3. Prints the secret to set as GITHUB_WEBHOOK_SECRET in .env and on
     Railway, then redeploy.
"""
from __future__ import annotations

import asyncio
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import get_settings
from backend.integrations.github import GitHubClient

DEFAULT_BACKEND_URL = "https://backend-production-e622.up.railway.app"


async def main() -> None:
    settings = get_settings()
    if not settings.github_token or not settings.github_repo:
        print("❌ GITHUB_TOKEN and GITHUB_REPO must be set in .env first.")
        sys.exit(1)

    backend_url = input(f"Deployed backend URL [{DEFAULT_BACKEND_URL}]: ").strip() or DEFAULT_BACKEND_URL
    target_url = f"{backend_url.rstrip('/')}/webhooks/github"

    client = GitHubClient()

    existing = await client.list_webhooks()
    for hook in existing:
        if hook.get("config", {}).get("url") == target_url:
            print(f"= A webhook already points at {target_url} (id={hook['id']}) — skipping creation.")
            print("  If you need to rotate the secret, delete it in the GitHub repo's Settings → Webhooks")
            print("  and re-run this script.")
            return

    webhook_secret = settings.github_webhook_secret or secrets.token_urlsafe(24)

    result = await client.create_webhook(
        target_url=target_url,
        secret=webhook_secret,
        events=["pull_request", "issues"],
    )
    print(f"✅ Created webhook id={result['id']} → {target_url}")
    print()
    print("Set this in .env and on Railway, then redeploy:")
    print(f"  GITHUB_WEBHOOK_SECRET={webhook_secret}")


if __name__ == "__main__":
    asyncio.run(main())
