"""Low-level client for shop.amul.com internal API."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    AMUL_BASE_URL,
    AMUL_PROTEIN_CATEGORY,
    AMUL_STORE_ID,
    KARNATAKA_SUBSTORE_ID,
)

logger = logging.getLogger(__name__)

PRODUCT_FIELDS = (
    "name",
    "alias",
    "sku",
    "price",
    "available",
    "inventory_quantity",
    "variants",
)

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{AMUL_BASE_URL}/en/browse/protein",
    "Origin": AMUL_BASE_URL,
    "frontend": "1",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}

SUBSTORE_IDS = {
    "karnataka": KARNATAKA_SUBSTORE_ID,
    "delhi": "66505ff5145c16635e6cc74d",
    "mumbai-br": "66506000c8f2d6e221b9193a",
    "pune-br": "66506004a7cddee1b8adb014",
}


@dataclass(frozen=True)
class PincodeRecord:
    pincode: str
    substore_alias: str


@dataclass(frozen=True)
class AmulProduct:
    name: str
    alias: str
    sku: str
    available: bool
    inventory_quantity: int
    price: float | None
    url: str

    @property
    def in_stock(self) -> bool:
        return self.available and self.inventory_quantity > 0


class AmulClient:
    """Authenticated session client for Amul's StoreHippo REST API."""

    def __init__(self, timeout: int = 30, max_retries: int = 3) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "PUT"),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self._session_tid: str | None = None
        self._store_version = "5"
        self._substore_alias: str | None = None
        self._substore_id: str | None = None
        self._initialized = False

    def initialize(self, pincode: str) -> PincodeRecord:
        """Create cookies, resolve pincode, and select the delivery substore."""
        if self._initialized:
            return PincodeRecord(
                pincode=pincode,
                substore_alias=self._substore_alias or "",
            )

        logger.info("Initializing Amul session...")
        self.session.get(f"{AMUL_BASE_URL}/en/browse/protein", timeout=self.timeout)
        self._load_session_tid()
        self._load_store_version()

        record = self._resolve_pincode(pincode)
        self._set_store_preference(record.substore_alias)
        self._substore_alias = record.substore_alias
        self._substore_id = self._lookup_substore_id(record.substore_alias)
        self._initialized = True

        logger.info(
            "Amul session ready for pincode %s (substore: %s)",
            record.pincode,
            record.substore_alias,
        )
        return record

    def fetch_protein_products(self) -> list[AmulProduct]:
        if not self._initialized:
            raise RuntimeError("Call initialize() before fetching products.")

        params: list[tuple[str, str]] = []
        for field in PRODUCT_FIELDS:
            params.append((f"fields[{field}]", "1"))

        params.extend(
            [
                ("filters[0][field]", "categories"),
                ("filters[0][value][0]", AMUL_PROTEIN_CATEGORY),
                ("filters[0][operator]", "in"),
                ("filters[0][original]", "1"),
                ("facets", "true"),
                ("facetgroup", "default_category_facet"),
                ("limit", "100"),
                ("total", "1"),
                ("start", "0"),
                ("v", self._store_version),
                ("device_type", "other"),
            ]
        )

        if self._substore_id:
            params.append(("substore", self._substore_id))

        query = urlencode(params).replace("%5B", "[").replace("%5D", "]")
        url = f"{AMUL_BASE_URL}/api/1/entity/ms.products?{query}"

        response = self.session.get(
            url,
            headers={"tid": self._calculate_tid()},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        return [self._parse_product(item) for item in payload.get("data", [])]

    def _load_session_tid(self) -> None:
        response = self.session.get(
            f"{AMUL_BASE_URL}/user/info.js?_v={int(time.time() * 1000)}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        session = json.loads(response.text.replace("session = ", "", 1))
        self._session_tid = session["tid"]

    def _load_store_version(self) -> None:
        try:
            response = self.session.get(
                f"{AMUL_BASE_URL}/ms/store/amul/auto/EN/storeinfo.js",
                timeout=self.timeout,
            )
            response.raise_for_status()
            match = re.search(
                r"req\.query\.v\s*=\s*['\"]?([^'\";\s]+)['\"]?",
                response.text,
            )
            if match:
                self._store_version = match.group(1)
        except requests.RequestException as exc:
            logger.warning("Could not fetch store version, using default: %s", exc)

    def _resolve_pincode(self, pincode: str) -> PincodeRecord:
        url = (
            f"{AMUL_BASE_URL}/entity/pincode"
            f"?limit=50&filters[0][field]=pincode"
            f"&filters[0][value]={pincode}&filters[0][operator]=regex&cf_cache=1h"
        )
        response = self.session.get(
            url,
            headers={"tid": self._calculate_tid()},
            timeout=self.timeout,
        )
        response.raise_for_status()
        records = response.json().get("records", [])
        if not records:
            raise ValueError(f"No delivery substore found for pincode {pincode}.")

        record = records[0]
        return PincodeRecord(
            pincode=str(record["pincode"]),
            substore_alias=str(record["substore"]),
        )

    def _set_store_preference(self, substore_alias: str) -> None:
        response = self.session.put(
            f"{AMUL_BASE_URL}/entity/ms.settings/_/setPreferences",
            json={"data": {"store": substore_alias}},
            headers={"tid": self._calculate_tid()},
            timeout=self.timeout,
        )
        response.raise_for_status()

    def _lookup_substore_id(self, substore_alias: str) -> str:
        substore_id = SUBSTORE_IDS.get(substore_alias)
        if substore_id:
            return substore_id

        logger.warning(
            "Unknown substore alias %r; using Karnataka substore ID as fallback.",
            substore_alias,
        )
        return KARNATAKA_SUBSTORE_ID

    def _calculate_tid(self) -> str:
        if not self._session_tid:
            raise RuntimeError("Session TID is not initialized.")

        timestamp = str(int(time.time() * 1000))
        rand = str(int(1000 * random.random()))
        payload = f"{AMUL_STORE_ID}:{timestamp}:{rand}:{self._session_tid}".encode()
        digest = hashlib.sha256(payload).hexdigest()
        return f"{timestamp}:{rand}:{digest}"

    @staticmethod
    def _parse_product(item: dict[str, Any]) -> AmulProduct:
        alias = str(item.get("alias", ""))
        available_raw = item.get("available", False)
        available = bool(available_raw) and str(available_raw) not in {"0", "false"}

        quantity_raw = item.get("inventory_quantity", 0)
        try:
            inventory_quantity = int(quantity_raw)
        except (TypeError, ValueError):
            inventory_quantity = 0

        price_raw = item.get("price")
        price = float(price_raw) if price_raw is not None else None

        return AmulProduct(
            name=str(item.get("name", alias)),
            alias=alias,
            sku=str(item.get("sku", "")),
            available=available,
            inventory_quantity=inventory_quantity,
            price=price,
            url=f"{AMUL_BASE_URL}/en/product/{alias}",
        )
