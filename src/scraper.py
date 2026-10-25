"""Scrape product data from Books to Scrape, a practice website.

The module is split into small pieces so each can be tested without a network:
  * ``parse_listing`` / ``parse_detail``  - pure HTML -> dict functions
  * ``fetch_soup``                        - HTTP with retries and backoff
  * ``robots_allows``                     - robots.txt check
  * ``scrape_books``                      - orchestration (pagination + detail pages)
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from src.http import USER_AGENT, get_response, new_session

BASE_URL = "https://books.toscrape.com/"
SOURCE_NAME = "books_toscrape"
LOGGER = logging.getLogger(__name__)

RATING_MAP = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


# ---------------------------------------------------------------- parsing
def _parse_price(text: str) -> str:
    """Keep only the numeric part, whatever currency symbol/mojibake precedes it."""
    match = re.search(r"\d+(?:[.,]\d+)?", text)
    return match.group(0).replace(",", ".") if match else ""


def parse_listing(soup: BeautifulSoup, page_url: str) -> tuple[list[dict], str | None]:
    """Extract product cards from one listing page. Returns (rows, next_page_url)."""
    rows: list[dict] = []
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for card in soup.select("article.product_pod"):
        title_tag = card.select_one("h3 a")
        price_tag = card.select_one(".price_color")
        if not title_tag or not price_tag:
            LOGGER.warning("Skipping a product card with missing title/price")
            continue

        availability_tag = card.select_one(".availability")
        rating_tag = card.select_one("p.star-rating")
        rating_word = next(
            (c for c in (rating_tag.get("class", []) if rating_tag else []) if c in RATING_MAP),
            "",
        )
        rows.append({
            "source": SOURCE_NAME,
            "title": title_tag.get("title") or title_tag.get_text(strip=True),
            "price": _parse_price(price_tag.get_text(strip=True)),
            "currency": "GBP",
            "availability": " ".join(availability_tag.stripped_strings) if availability_tag else "Unknown",
            "rating": RATING_MAP.get(rating_word),
            "category": "",
            "sku": "",
            "product_url": urljoin(page_url, title_tag.get("href", "")),
            "source_url": page_url,
            "scraped_at_utc": scraped_at,
        })

    next_link = soup.select_one("li.next a")
    next_url = urljoin(page_url, next_link.get("href")) if next_link else None
    return rows, next_url


def parse_detail(soup: BeautifulSoup) -> dict:
    """Extract category (from the breadcrumb) and SKU (UPC, from the product table)."""
    crumbs = [li.get_text(strip=True) for li in soup.select("ul.breadcrumb li")]
    # Breadcrumb: Home > Books > <Category> > <Title>
    category = crumbs[2] if len(crumbs) >= 4 else ""

    sku = ""
    for row in soup.select("table.table-striped tr"):
        th, td = row.select_one("th"), row.select_one("td")
        if th and td and th.get_text(strip=True).upper() == "UPC":
            sku = td.get_text(strip=True)
            break
    return {"category": category, "sku": sku}


# ---------------------------------------------------------------- network
def fetch_soup(url: str, session: requests.Session) -> BeautifulSoup:
    """Fetch one page and parse it."""
    response = get_response(url, session)
    # Raw bytes + explicit UTF-8: response.text would guess ISO-8859-1 for this
    # site and turn "£" into "Â£".
    return BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")


def robots_allows(base_url: str, session: requests.Session) -> bool:
    """True if robots.txt permits our user agent to fetch the site root.

    A missing robots.txt (404) means no restrictions. If it cannot be fetched at
    all we stay conservative and say no.
    """
    robots_url = urljoin(base_url, "/robots.txt")
    try:
        response = session.get(robots_url, timeout=10)
    except requests.RequestException as exc:
        LOGGER.warning("Could not read %s (%s); not scraping.", robots_url, exc)
        return False
    if response.status_code in (404, 410):
        return True
    if not response.ok:
        return False
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, base_url)


# ---------------------------------------------------------------- orchestration
def scrape_books(
    max_pages: int | None = None,
    delay_seconds: float = 0.25,
    with_details: bool = False,
    base_url: str = BASE_URL,
) -> list[dict]:
    """Collect products across paginated listing pages.

    max_pages     limit pages for a quick run; None follows pagination to the end.
    with_details  also open each product page to read category and SKU
                  (one extra request per product, so much slower).
    """
    rows: list[dict] = []
    visited: set[str] = set()
    current_url: str | None = base_url

    with new_session() as session:
        if not robots_allows(base_url, session):
            raise RuntimeError(f"robots.txt does not allow scraping {urlparse(base_url).netloc}")

        page_count = 0
        while current_url and current_url not in visited:
            if max_pages is not None and page_count >= max_pages:
                break
            visited.add(current_url)
            soup = fetch_soup(current_url, session)
            page_count += 1
            page_rows, next_url = parse_listing(soup, current_url)
            LOGGER.info("Page %s: %s products (%s)", page_count, len(page_rows), current_url)

            if with_details:
                for row in page_rows:
                    try:
                        row.update(parse_detail(fetch_soup(row["product_url"], session)))
                    except RuntimeError as exc:  # keep the listing data, skip details
                        LOGGER.warning("Detail page skipped: %s", exc)
                    time.sleep(max(0.0, delay_seconds))

            rows.extend(page_rows)
            current_url = next_url
            if current_url:
                time.sleep(max(0.0, delay_seconds))

    return rows
