#!/usr/bin/env python3
"""One-time setup for the Discord community bot (#9): registers the
/github, /tasks and /weekly slash commands globally via Discord's REST
API. Also resolves DISCORD_APPLICATION_ID and DISCORD_PUBLIC_KEY from
DISCORD_BOT_TOKEN via GET /oauth2/applications/@me (its `id` and
`verify_key` fields) if they aren't already set, so no Developer Portal
copy-pasting is needed for those either.

    python scripts/discord_commands_setup.py

Prerequisite: DISCORD_BOT_TOKEN set in .env.
Global commands can take up to an hour to appear in Discord the first
time; edits to already-registered commands propagate faster.

The one step this script genuinely cannot do: setting the Interactions
Endpoint URL in the Developer Portal. Discord sends a live PING to that
URL to verify it before letting you save the field, and there is no API
that lets a third party set it on your behalf.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import get_settings

COMMANDS = [
    {
        "name": "github",
        "description": "Recent commit activity on the configured repo (last 7 days)",
        "type": 1,
    },
    {
        "name": "tasks",
        "description": "Todoist tasks completed this week",
        "type": 1,
    },
    {
        "name": "weekly",
        "description": "Generate and post the weekly status report",
        "type": 1,
    },
]


def _resolve_application_identity(bot_token: str) -> tuple[str, str]:
    """Looks up this bot's application id + Ed25519 verify_key so the
    caller doesn't have to copy them from the Developer Portal by hand."""
    resp = httpx.get(
        "https://discord.com/api/v10/oauth2/applications/@me",
        headers={"Authorization": f"Bot {bot_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["id"], data["verify_key"]


def main() -> None:
    settings = get_settings()
    if not settings.discord_bot_token:
        print("❌ DISCORD_BOT_TOKEN must be set in .env first.")
        sys.exit(1)

    application_id = settings.discord_application_id
    public_key = settings.discord_public_key
    if not application_id or not public_key:
        try:
            application_id, public_key = _resolve_application_identity(settings.discord_bot_token)
            print(f"✅ Resolved application id and public key from the bot token.")
            print(f"   Set these in .env and on Railway:")
            print(f"     DISCORD_APPLICATION_ID={application_id}")
            print(f"     DISCORD_PUBLIC_KEY={public_key}")
        except Exception as exc:
            print(f"❌ Could not resolve application identity from DISCORD_BOT_TOKEN: {exc}")
            sys.exit(1)

    url = f"https://discord.com/api/v10/applications/{application_id}/commands"
    headers = {"Authorization": f"Bot {settings.discord_bot_token}"}

    resp = httpx.put(url, headers=headers, json=COMMANDS, timeout=15)
    if resp.status_code >= 300:
        print(f"❌ Failed to register commands ({resp.status_code}): {resp.text}")
        sys.exit(1)

    registered = resp.json()
    print(f"✅ Registered {len(registered)} global slash commands:")
    for cmd in registered:
        print(f"   /{cmd['name']} — {cmd['description']}")
    print()
    print("Note: global commands can take up to ~1 hour to first appear in Discord.")
    print()
    print("Remaining manual step (no API for this): in the Discord Developer Portal,")
    print("under your app → General Information, set the Interactions Endpoint URL to:")
    print("  https://backend-production-e622.up.railway.app/discord/interactions")
    print("Discord will send a live PING to verify it before letting you save — the")
    print("backend must already be deployed with DISCORD_PUBLIC_KEY set for that to")
    print("succeed.")


if __name__ == "__main__":
    main()
