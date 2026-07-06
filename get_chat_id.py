"""Print your Telegram chat ID after you message the bot."""

from __future__ import annotations

import sys

import requests

from config import get_settings, validate_settings


def main() -> int:
    try:
        settings = get_settings()
        validate_settings(settings)
    except ValueError as exc:
        print(exc)
        return 1

    bot_id = settings.bot_token.split(":", 1)[0]
    if settings.chat_id == bot_id:
        print(
            "CHAT_ID is set to your bot's ID, not your personal chat ID.\n"
            f"Message @{_bot_username(settings)} on Telegram, then run this script again.\n"
        )

    response = requests.get(
        f"https://api.telegram.org/bot{settings.bot_token}/getUpdates",
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    if not payload.get("ok"):
        print("Telegram API error:", payload)
        return 1

    for update in payload.get("result", []):
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if chat_id and chat.get("type") == "private":
            name = chat.get("first_name") or chat.get("username") or "user"
            print(f"Your CHAT_ID is: {chat_id}  ({name})")
            print(f"\nAdd this to .env:\nCHAT_ID={chat_id}")
            return 0

    username = _bot_username(settings)
    print(
        "No messages found yet.\n"
        f"1. Open Telegram and message @{username} (send anything, e.g. hi)\n"
        "2. Run: python3 get_chat_id.py"
    )
    return 1


def _bot_username(settings) -> str:
    response = requests.get(
        f"https://api.telegram.org/bot{settings.bot_token}/getMe",
        timeout=30,
    )
    if response.ok:
        return response.json().get("result", {}).get("username", "your_bot")
    return "your_bot"


if __name__ == "__main__":
    sys.exit(main())
