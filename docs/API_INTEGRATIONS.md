# API Integration Setup Guide

Everything runs in `MOCK_MODE=true` with zero credentials today — every
integration client in `backend/integrations/` returns realistic canned
data when mock mode is on or a key is missing. This doc is what to do
**when you're ready to go live** with each of these APIs. You don't have
to do them all at once — flip them on one at a time; each integration
falls back to mock behavior independently based on whether its specific
key is set (once `MOCK_MODE=false`).

Set `MOCK_MODE=false` in `.env` once you've filled in the credentials you
care about. Any integration whose key is still blank will keep behaving
like mock mode (see the `or not settings.xxx_key` checks in each client).

---

## 1. Gmail + Google Calendar + Google Sheets (shared OAuth)

These three share one OAuth "Desktop app" client since they're all Google
APIs.

1. Go to https://console.cloud.google.com/apis/credentials (create a
   project if you don't have one).
2. Enable these APIs under "APIs & Services → Library": **Gmail API**,
   **Google Calendar API**, **Google Sheets API**.
3. "Create Credentials" → **OAuth client ID** → Application type:
   **Desktop app**. Download the JSON.
4. Save it at the path in `.env` as `GOOGLE_CREDENTIALS_PATH`
   (default `./credentials/google_credentials.json`).
5. Run the one-time auth flow (opens a browser, asks you to consent):

   ```bash
   python scripts/google_auth_setup.py
   ```

   This writes a refresh token to `GOOGLE_TOKEN_PATH`
   (`./credentials/google_token.json`), which is reused and silently
   refreshed on every run after that — you only do this once.
6. Set `CALENDAR_IDS` in `.env` (comma-separated) if you want to check
   more than your primary calendar, e.g. `primary,work@company.com`.
7. For Sheets: create a spreadsheet, copy its ID from the URL
   (`.../spreadsheets/d/<THIS_PART>/edit`), set
   `GOOGLE_SHEETS_SPREADSHEET_ID`.

## 2. Slack

1. Create an app at https://api.slack.com/apps → "From scratch".
2. Under **OAuth & Permissions**, add these Bot Token Scopes:
   `chat:write`, `reactions:write`, `channels:read`.
3. Install the app to your workspace, copy the **Bot User OAuth Token**
   (`xoxb-...`) into `SLACK_BOT_TOKEN`.
4. Create the three channels referenced in `.env` (or rename the env vars
   to channels you already have): `#agent-approvals`, `#agent-activity`,
   `#agent-conflicts`. Invite the bot to each (`/invite @YourBotName`).
5. For the Approve/Reject buttons to work: under **Interactivity &
   Shortcuts**, turn it on and set the Request URL to
   `https://<your-deployed-backend>/webhooks/slack/interactivity`
   (needs a public URL — use `ngrok http 8000` for local testing).
6. Copy the **Signing Secret** (Basic Information page) into
   `SLACK_SIGNING_SECRET` — this is what verifies the interactivity
   webhook actually came from Slack.

## 3. Todoist

1. Settings → Integrations → Developer → copy your **API token**.
2. Set `TODOIST_API_KEY`.

## 4. Notion (knowledge graph)

1. Create an integration at https://www.notion.so/my-integrations, copy
   the **Internal Integration Token** into `NOTION_API_KEY`.
2. Create a database in Notion for decisions with these exact properties
   (names and types matter — `knowledge_graph_agent.py` writes to them
   directly):
   - `Title` — Title
   - `Agent` — Select
   - `Decision Type` — Select
   - `Timestamp` — Date
   - `Reasoning Trace` — Text
3. Share the database with your integration (••• menu → Add connections).
4. Copy the database ID from its URL into `NOTION_DECISIONS_DB_ID`.

Note: the local SQLite/Postgres mirror (`KnowledgeEntity` /
`KnowledgeRelationship` tables) always works regardless of Notion, so the
dashboard's graph view and pattern learning ("Alex prefers mornings")
don't depend on this being configured.

## 5. GitHub (bonus DevOps agent)

1. Create a fine-grained personal access token with `Issues: Read and
   write` on the target repo.
2. Set `GITHUB_TOKEN` and `GITHUB_REPO` (`owner/repo` format).

## 6. Telegram (bonus alert agent)

1. Message **@BotFather** on Telegram, `/newbot`, copy the token into
   `TELEGRAM_BOT_TOKEN`.
2. Message your new bot once, then fetch
   `https://api.telegram.org/bot<token>/getUpdates` to find your
   `chat.id`, set it as `TELEGRAM_CHAT_ID`.

## 7. Discord (bonus social agent)

Two ways to do this — pick one. If both are set, the bot-token path wins.

**Option A — bot token + channel ID (more flexible, posts to any channel
the bot is in):**

1. https://discord.com/developers/applications → New Application → Bot →
   copy the token into `DISCORD_BOT_TOKEN`.
2. OAuth2 → URL Generator → scope `bot`, permission `Send Messages` →
   open the generated URL to invite it to your server.
3. In Discord, enable **Settings → Advanced → Developer Mode**, then
   right-click the target channel → **Copy Channel ID** → set
   `DISCORD_CHANNEL_ID`.

**Option B — incoming webhook (simpler, one URL per channel):**

1. Server Settings → Integrations → Webhooks → New Webhook.
2. Copy the webhook URL into `DISCORD_WEBHOOK_URL`.

## 8. NVIDIA NIM (semantic intent extraction)

1. Get a free API key from https://build.nvidia.com (any model card →
   "Get API Key"), set `NVIDIA_API_KEY`.
2. `NVIDIA_MODEL` defaults to `openai/gpt-oss-20b`, confirmed working on
   a free-tier key. Not every model `GET /v1/models` lists is actually
   enabled for a given account (some 404 with "Function ... Not found
   for account", others 410 if NVIDIA retired that endpoint) — if you
   swap models, test it directly before assuming it works:
   ```bash
   curl -s https://integrate.api.nvidia.com/v1/chat/completions \
     -H "Authorization: Bearer $NVIDIA_API_KEY" -H "Content-Type: application/json" \
     -d '{"model": "your/model-slug", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}'
   ```
3. The API is OpenAI-compatible (`POST /v1/chat/completions`), called
   directly via httpx in `backend/utils/llm.py` — no extra SDK.
4. Without a key, `utils/llm.py` uses a deterministic keyword-based
   heuristic instead — good enough to exercise the pipeline, but it's not
   "semantic understanding," just a stand-in for it.

---

## Verifying a specific integration went live

Each client logs a structured error via `structlog` if a real API call
fails (auth, rate limit, etc.) — watch the backend's stdout. You can also
call an agent directly in a Python shell:

```python
from backend.integrations.notion import NotionClient
import asyncio
client = NotionClient()
print(asyncio.run(client.create_page("<your-db-id>", {...})))
```

If nothing changed after setting a key, double check `MOCK_MODE=false`
in `.env` — the flag is the master switch; per-key fallback only kicks in
once it's off.
