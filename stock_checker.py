"""Stock checking logic for watched Amul products."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from amul_client import AmulClient, AmulProduct
from config import WATCHED_PRODUCTS, Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StockStatus:
    product: AmulProduct
    label: str
    in_stock: bool


class StockChecker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AmulClient(
            timeout=settings.request_timeout,
            max_retries=settings.max_retries,
        )
        self._client_ready = False

    def check(self) -> list[StockStatus]:
        logger.info("Checking stock for pincode %s...", self.settings.pincode)

        if not self._client_ready:
            self.client.initialize(self.settings.pincode)
            self._client_ready = True

        products = self.client.fetch_protein_products()
        watched = self._filter_watched_products(products)

        if not watched:
            logger.warning("No watched lassi products found in API response.")
            return []

        statuses: list[StockStatus] = []
        for label, product in watched:
            status = StockStatus(
                product=product,
                label=label,
                in_stock=product.in_stock,
            )
            statuses.append(status)
            state = "In stock" if status.in_stock else "Out of stock"
            logger.info(
                "%s (%s): %s [qty=%s]",
                product.name,
                product.sku,
                state,
                product.inventory_quantity,
            )

        return statuses

    @staticmethod
    def _filter_watched_products(
        products: Iterable[AmulProduct],
    ) -> list[tuple[str, AmulProduct]]:
        matched: list[tuple[str, AmulProduct]] = []

        for watch in WATCHED_PRODUCTS:
            needle = watch["match"]
            label = watch["label"]

            for product in products:
                if needle in product.alias.lower():
                    matched.append((label, product))
                    break

        return matched


class StockStateStore:
    """Persists last-known stock state to avoid duplicate notifications."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, bool]:
        if not self.path.exists():
            return {}

        try:
            with self.path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return {str(k): bool(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read state file %s: %s", self.path, exc)

        return {}

    def save(self, state: dict[str, bool]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)

    def detect_transitions(
        self,
        statuses: Iterable[StockStatus],
    ) -> list[StockStatus]:
        previous = self.load()
        current = {status.product.sku: status.in_stock for status in statuses}
        newly_available: list[StockStatus] = []

        for status in statuses:
            sku = status.product.sku
            was_in_stock = previous.get(sku, False)
            if status.in_stock and not was_in_stock:
                newly_available.append(status)

        self.save(current)
        return newly_available
