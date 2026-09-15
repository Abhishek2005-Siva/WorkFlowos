"""Central configuration, loaded from environment variables / .env."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Mode
    mock_mode: bool = True

    # NVIDIA NIM (semantic intent extraction — OpenAI-compatible API)
    nvidia_api_key: str = ""
    nvidia_model: str = "openai/gpt-oss-20b"

    # Google (Gmail + Calendar)
    google_credentials_path: str = "./credentials/google_credentials.json"
    google_token_path: str = "./credentials/google_token.json"
    calendar_ids: str = "primary"

    # Slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_approvals_channel: str = "#agent-approvals"
    slack_activity_channel: str = "#agent-activity"
    slack_conflicts_channel: str = "#agent-conflicts"

    # Todoist
    todoist_api_key: str = ""

    # Notion
    notion_api_key: str = ""
    notion_decisions_db_id: str = ""

    # GitHub
    github_token: str = ""
    github_repo: str = ""

    # Google Sheets
    google_sheets_spreadsheet_id: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Discord
    discord_bot_token: str = ""
    discord_channel_id: str = ""
    discord_webhook_url: str = ""

    # How long a workflow waits for a human to approve/reject before treating
    # it as rejected. Short in MOCK_MODE-style demos, needs to be realistic
    # (minutes) once a human is actually expected to click something.
    approval_timeout_seconds: float = 300.0

    # Background polling (off by default — trigger cycles from the dashboard instead)
    enable_auto_poll: bool = False
    poll_interval_seconds: int = 60

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./workflowos.db"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

    @property
    def calendar_id_list(self) -> list[str]:
        return [c.strip() for c in self.calendar_ids.split(",") if c.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
