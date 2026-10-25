"""Run extraction, cleaning, validation, quality reporting, and storage."""
from __future__ import annotations

import argparse
import logging

import pandas as pd

from src.api_source import API_URL, fetch_api_products
from src.quality import quality_report, save_report
from src.scraper import BASE_URL, scrape_books
from src.storage import save_outputs

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

COLUMNS = [
    "source", "title", "price", "currency", "availability", "rating", "category",
    "sku", "product_url", "source_url", "scraped_at_utc",
]


def clean_products(rows: list[dict]) -> pd.DataFrame:
    """Validate and normalise rows from any source into one schema."""
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None

    df["title"] = df["title"].astype("string").str.strip()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").round(2)
    df["availability"] = (df["availability"].fillna("Unknown").astype("string")
                          .str.strip().str.capitalize())          # "In Stock" -> "In stock"
    df["category"] = df["category"].fillna("").astype("string").str.strip().str.title()
    df["source"] = df["source"].fillna("unknown")
    df["currency"] = df["currency"].fillna("")
    df = df.dropna(subset=["title", "price"])
    df = df[(df["title"].str.len() > 0) & (df["price"] >= 0)]
    df = df.drop_duplicates(subset=["source", "product_url"], keep="last")
    return df[COLUMNS].reset_index(drop=True)


def collect(sources: list[str], *, max_pages: int | None, max_items: int | None, details: bool,
            delay: float, books_url: str, api_url: str) -> list[dict]:
    """Run each requested source; one failing source does not stop the others."""
    rows: list[dict] = []
    for name in sources:
        try:
            if name == "books":
                rows += scrape_books(max_pages=max_pages, delay_seconds=delay,
                                     with_details=details, base_url=books_url)
            elif name == "dummyjson":
                rows += fetch_api_products(api_url, max_items=max_items, delay_seconds=delay)
            else:
                logging.error("Unknown source %r (choose from: books, dummyjson)", name)
        except Exception as exc:  # noqa: BLE001 - report and continue with other sources
            logging.error("Source %s failed: %s", name, exc)
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Collect, clean and store product data from several sources.")
    ap.add_argument("--sources", default="books,dummyjson", help="comma list: books, dummyjson")
    ap.add_argument("--max-pages", type=int, default=None, help="books: stop after N listing pages")
    ap.add_argument("--max-items", type=int, default=None, help="dummyjson: stop after N items")
    ap.add_argument("--details", action="store_true", help="books: open each product page for category + SKU (slower)")
    ap.add_argument("--delay", type=float, default=0.25, help="seconds to wait between requests")
    ap.add_argument("--books-url", default=BASE_URL, help="override the books start URL (testing)")
    ap.add_argument("--api-url", default=API_URL, help="override the API URL (testing)")
    args = ap.parse_args(argv)

    rows = collect([s.strip() for s in args.sources.split(",") if s.strip()],
                   max_pages=args.max_pages, max_items=args.max_items, details=args.details,
                   delay=args.delay, books_url=args.books_url, api_url=args.api_url)
    df = clean_products(rows)
    if df.empty:
        raise SystemExit("No valid records collected. Check network access and the target page structure.")

    report = quality_report(len(rows), df)
    save_outputs(df)
    save_report(report)
    logging.info("Saved %s valid products (%s rejected) from %s source(s)",
                 report["valid_rows"], report["rejected_rows"], len(report["by_source"]))


if __name__ == "__main__":
    main()
