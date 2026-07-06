"""Configuration for the Amul stock notifier."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / ".stock_state.json"

# Pincode 560103 maps to the Karnataka substore on shop.amul.com.
DEFAULT_PINCODE = "560103"

# Products to monitor (matched by alias substring).
WATCHED_PRODUCTS = (
    {
        "match": "plain-lassi",
        "label": "Plain Protein Lassi",
    },
    {
        "match": "rose-lassi",
        "label": "Rose Protein Lassi",
    },
)

AMUL_BASE_URL = "https://shop.amul.com"
AMUL_STORE_ID = "62fa94df8c13af2e242eba16"
AMUL_PROTEIN_CATEGORY = "protein"

# Karnataka substore ID (resolved automatically from pincode; kept as fallback).
KARNATAKA_SUBSTORE_ID = "66505ff0998183e1b1935c75"


@dataclass(frozen=True)
class Settings:
    bot_token: str
    chat_id: str
    poll_interval: int = 300
    pincode: str = DEFAULT_PINCODE
    state_file: Path = STATE_FILE
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 2.0


def get_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("CHAT_ID", "").strip()
    poll_interval = int(os.getenv("POLL_INTERVAL", "300"))
    pincode = os.getenv("PINCODE", DEFAULT_PINCODE).strip()

    return Settings(
        bot_token=bot_token,
        chat_id=chat_id,
        poll_interval=poll_interval,
        pincode=pincode,
    )


def validate_settings(settings: Settings) -> None:
    if not settings.bot_token:
        raise ValueError("BOT_TOKEN is missing. Add it to your .env file.")
    if not settings.chat_id:
        raise ValueError("CHAT_ID is missing. Add it to your .env file.")

    if ":" in settings.bot_token:
        bot_id = settings.bot_token.split(":", 1)[0]
        if settings.chat_id == bot_id:
            raise ValueError(
                "CHAT_ID is set to your bot's ID, not your personal chat ID. "
                "Message your bot on Telegram, then run: python3 get_chat_id.py"
            )
