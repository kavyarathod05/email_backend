"""Internship intel settings — reads from the same Render .env as outreach."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class IntelSettings:
    """Optional vars for internship discovery. Mongo reuses outreach connection."""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    slack_webhook_url: str = ""
    scheduler_secret: str = ""


def get_settings() -> IntelSettings:
    return IntelSettings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""),
        scheduler_secret=os.getenv("SCHEDULER_SECRET", ""),
    )
