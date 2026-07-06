"""Main entry point for the Amul stock notifier."""

from __future__ import annotations

import argparse
import logging
import sys
import time

import requests

from config import get_settings, validate_settings
from notifier import TelegramNotifier
from stock_checker import StockChecker, StockStateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_check() -> int:
    settings = get_settings()

    try:
        validate_settings(settings)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    checker = StockChecker(settings)
    state_store = StockStateStore(settings.state_file)
    notifier = TelegramNotifier(settings)

    try:
        statuses = checker.check()
    except requests.RequestException as exc:
        logger.error("Network error while checking stock: %s", exc)
        return 1
    except ValueError as exc:
        logger.error("Configuration or API error: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Unexpected error while checking stock: %s", exc)
        return 1

    if not statuses:
        logger.warning("No products to monitor in this check cycle.")
        return 0

    newly_available = state_store.detect_transitions(statuses)

    for status in newly_available:
        try:
            notifier.send_stock_alert(status)
        except ValueError as exc:
            logger.error("%s", exc)
            return 1
        except requests.RequestException as exc:
            logger.error("Failed to send Telegram notification: %s", exc)
            return 1

    if not newly_available:
        logger.info("No new in-stock alerts this cycle.")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor Amul Protein Lassi stock and send Telegram alerts.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single check and exit (for CI/cron).",
    )
    args = parser.parse_args()

    if args.once:
        return run_check()

    settings = get_settings()
    try:
        validate_settings(settings)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    logger.info(
        "Starting stock monitor (pincode=%s, interval=%ss)",
        settings.pincode,
        settings.poll_interval,
    )

    while True:
        exit_code = run_check()
        if exit_code != 0:
            logger.warning("Check failed; retrying in %ss", settings.retry_delay)
            time.sleep(settings.retry_delay)
        else:
            time.sleep(settings.poll_interval)


if __name__ == "__main__":
    sys.exit(main())
