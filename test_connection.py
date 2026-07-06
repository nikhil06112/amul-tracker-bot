"""Smoke tests for website API and Telegram connectivity."""

from __future__ import annotations

import argparse
import logging
import sys

import requests

from amul_client import AmulClient
from config import WATCHED_PRODUCTS, get_settings, validate_settings
from notifier import TelegramNotifier
from stock_checker import StockChecker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def test_website_reachable(timeout: int = 30) -> None:
    logger.info("Testing website reachability...")
    response = requests.get(
        "https://shop.amul.com/en/browse/protein",
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    logger.info("Website reachable (HTTP %s)", response.status_code)


def test_product_endpoint(settings) -> None:
    logger.info("Testing product API for pincode %s...", settings.pincode)
    client = AmulClient(timeout=settings.request_timeout)
    client.initialize(settings.pincode)
    products = client.fetch_protein_products()

    if not products:
        raise RuntimeError("Product API returned no protein products.")

    aliases = {product.alias.lower() for product in products}
    missing = [
        watch["label"]
        for watch in WATCHED_PRODUCTS
        if not any(watch["match"] in alias for alias in aliases)
    ]
    if missing:
        raise RuntimeError(f"Watched products not found: {', '.join(missing)}")

    logger.info("Product API OK (%s protein products found)", len(products))


def test_stock_checker(settings) -> None:
    logger.info("Testing stock checker...")
    statuses = StockChecker(settings).check()
    if not statuses:
        raise RuntimeError("Stock checker returned no watched products.")
    for status in statuses:
        state = "in stock" if status.in_stock else "out of stock"
        logger.info("%s is %s", status.product.name, state)


def test_telegram(settings) -> None:
    logger.info("Testing Telegram messaging...")
    TelegramNotifier(settings).send_test_message()
    logger.info("Telegram test message sent")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Amul stock notifier smoke tests.")
    parser.add_argument(
        "--skip-telegram",
        action="store_true",
        help="Skip Telegram test (useful without credentials).",
    )
    args = parser.parse_args()

    settings = get_settings()

    try:
        test_website_reachable(settings.request_timeout)
        test_product_endpoint(settings)
        test_stock_checker(settings)

        if not args.skip_telegram:
            validate_settings(settings)
            test_telegram(settings)
        else:
            logger.info("Skipping Telegram test.")

        logger.info("All tests passed.")
        return 0
    except Exception as exc:
        logger.error("Test failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
