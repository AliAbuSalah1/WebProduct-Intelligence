"""Second source: a public JSON product API intended for testing (DummyJSON).

Together with the HTML scraper this makes the pipeline multi-source: two different
site structures, two currencies, two availability vocabularies, one common schema.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from src.http import get_response, new_session

SOURCE_NAME = "dummyjson"
API_URL = "https://dummyjson.com/products"
PRODUCT_URL = "https://dummyjson.com/products/{id}"
LOGGER = logging.getLogger(__name__)


def parse_product(item: dict, source_url: str, scraped_at: str) -> dict | None:
    """Map one API item to the common schema; None if it has no id/title/price."""
    if item.get("id") is None or not item.get("title") or item.get("price") is None:
        return None
    stock = item.get("stock")
    availability = item.get("availabilityStatus") or (
        "Unknown" if stock is None else ("In stock" if stock > 0 else "Out of stock")
    )
    return {
        "source": SOURCE_NAME,
        "title": item["title"],
        "price": item["price"],
        "currency": "USD",
        "availability": availability,
        "rating": item.get("rating"),
        "category": item.get("category") or "",
        "sku": item.get("sku") or "",
        "product_url": PRODUCT_URL.format(id=item["id"]),
        "source_url": source_url,
        "scraped_at_utc": scraped_at,
    }


def fetch_api_products(api_url: str = API_URL, page_size: int = 50, max_items: int | None = None,
                       delay_seconds: float = 0.25) -> list[dict]:
    """Page through the API with limit/skip until `total` items have been read."""
    rows: list[dict] = []
    skip = 0
    with new_session() as session:
        while True:
            payload = get_response(api_url, session, params={"limit": page_size, "skip": skip}).json()
            items = payload.get("products", [])
            scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for item in items:
                row = parse_product(item, api_url, scraped_at)
                if row:
                    rows.append(row)
                else:
                    LOGGER.warning("Skipping malformed API item: %s", item.get("id"))
            LOGGER.info("API page skip=%s: %s items", skip, len(items))
            skip += len(items)
            if not items or skip >= payload.get("total", 0):
                break
            if max_items is not None and len(rows) >= max_items:
                break
            time.sleep(max(0.0, delay_seconds))
    return rows[:max_items] if max_items is not None else rows
