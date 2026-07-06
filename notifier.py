"""Telegram notification sender."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from config import Settings
from stock_checker import StockStatus

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_url = f"{TELEGRAM_API_BASE}/bot{settings.bot_token}"

    def send_stock_alert(self, status: StockStatus) -> None:
        now = datetime.now(timezone.utc).astimezone()
        message = (
            "🚨 Amul Protein Lassi is back in stock!\n\n"
            f"Product: {status.product.name}\n"
            f"Variant: {status.label}\n"
            f"Quantity: {status.product.inventory_quantity}\n"
            f"Pincode: {self.settings.pincode}\n"
            f"Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"URL: {status.product.url}"
        )
        self._send_message(message)
        logger.info("Notification sent for %s", status.product.sku)

    def send_test_message(self) -> None:
        message = (
            "✅ Amul stock notifier is connected.\n"
            f"Monitoring pincode {self.settings.pincode} for "
            "Plain and Rose Protein Lassi."
        )
        self._send_message(message)

    def _send_message(self, text: str) -> None:
        response = requests.post(
            f"{self.api_url}/sendMessage",
            json={
                "chat_id": self.settings.chat_id,
                "text": text,
                "disable_web_page_preview": False,
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Telegram API error ({response.status_code}): {response.text}"
            )

        payload = response.json()
        if not payload.get("ok"):
            description = payload.get("description", "Unknown error")
            if "chat not found" in description.lower():
                raise ValueError(
                    "Invalid CHAT_ID or bot has not been started in that chat."
                )
            if "unauthorized" in description.lower():
                raise ValueError("Invalid BOT_TOKEN.")
            raise RuntimeError(f"Telegram API rejected message: {description}")
