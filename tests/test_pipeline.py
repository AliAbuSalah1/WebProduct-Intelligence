import sqlite3

import pandas as pd
from bs4 import BeautifulSoup

from src.api_source import parse_product
from src.pipeline import clean_products
from src.quality import quality_report
from src.scraper import _parse_price, parse_detail, parse_listing
from src.storage import SQL_DIR, save_outputs, run_sql_file

LISTING_HTML = """
<html><body>
<article class="product_pod">
  <p class="star-rating Three"></p>
  <h3><a href="book_1/index.html" title="A Light in the Attic">A Light in the ...</a></h3>
  <div class="product_price"><p class="price_color">£51.77</p>
  <p class="instock availability"><i></i> In stock </p></div>
</article>
<article class="product_pod"><h3><a href="x.html" title="No price"></a></h3></article>
<ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>
</body></html>
"""

DETAIL_HTML = """
<ul class="breadcrumb"><li><a>Home</a></li><li><a>Books</a></li>
<li><a>Poetry</a></li><li class="active">A Light in the Attic</li></ul>
<table class="table table-striped"><tr><th>UPC</th><td>a897fe39b1053632</td></tr></table>
"""


def row(**kw):
    base = {"source": "s", "title": "Book A", "price": "12.50", "currency": "GBP",
            "availability": "In stock", "rating": 4, "category": "Poetry",
            "product_url": "https://example.test/a", "source_url": "u",
            "scraped_at_utc": "2026-01-01T00:00:00+00:00"}
    base.update(kw)
    return base


# ---- cleaning
def test_clean_products_converts_prices_and_removes_duplicates():
    df = clean_products([row(), row(title="Book A duplicate"),
                         row(title="Bad price", price="not-a-price", product_url="https://example.test/b")])
    assert len(df) == 1
    assert float(df.iloc[0]["price"]) == 12.5
    assert df.iloc[0]["title"] == "Book A duplicate"


def test_same_url_in_two_sources_is_not_a_duplicate():
    assert len(clean_products([row(source="x"), row(source="y")])) == 2


def test_clean_normalises_availability_and_category():
    df = clean_products([row(availability=" In Stock ", category="smartphones")])
    assert df.iloc[0]["availability"] == "In stock"
    assert df.iloc[0]["category"] == "Smartphones"


def test_clean_products_empty_input_has_expected_columns():
    df = clean_products([])
    assert {"source", "title", "price", "currency"} <= set(df.columns) and len(df) == 0


# ---- HTML scraper parsing
def test_parse_price_handles_mojibake_and_symbols():
    assert _parse_price("£51.77") == "51.77"
    assert _parse_price("Â£51.77") == "51.77"
    assert _parse_price("n/a") == ""


def test_parse_listing_extracts_cards_and_next_link():
    rows, nxt = parse_listing(BeautifulSoup(LISTING_HTML, "html.parser"), "https://s.test/catalogue/page-1.html")
    assert len(rows) == 1  # card without a price is skipped
    assert rows[0]["title"] == "A Light in the Attic"
    assert rows[0]["price"] == "51.77" and rows[0]["currency"] == "GBP" and rows[0]["rating"] == 3
    assert rows[0]["product_url"] == "https://s.test/catalogue/book_1/index.html"
    assert nxt == "https://s.test/catalogue/page-2.html"


def test_parse_detail_reads_category_and_sku():
    assert parse_detail(BeautifulSoup(DETAIL_HTML, "html.parser")) == {
        "category": "Poetry", "sku": "a897fe39b1053632"}


# ---- API source parsing
def test_parse_api_product_maps_to_common_schema():
    item = {"id": 7, "title": "Phone", "price": 199.99, "category": "smartphones", "rating": 4.37,
            "stock": 5, "availabilityStatus": "Low Stock", "sku": "PH-7"}
    r = parse_product(item, "https://api.test/products", "2026-01-01T00:00:00+00:00")
    assert r["source"] == "dummyjson" and r["currency"] == "USD" and r["price"] == 199.99
    assert r["product_url"].endswith("/products/7")
    assert parse_product({"id": 1, "title": "x"}, "u", "t") is None  # no price


# ---- storage, history, SQL, quality
def _save_run(db, csv, price, at):
    df = clean_products([row(price=str(price), scraped_at_utc=at),
                         row(title="Book B", price="20", rating=5, product_url="https://example.test/b",
                             scraped_at_utc=at)])
    save_outputs(df, csv, db)


def test_history_is_appended_and_price_changes_detected(tmp_path):
    db, csv = tmp_path / "p.db", tmp_path / "p.csv"
    _save_run(db, csv, 10, "2026-01-01T00:00:00+00:00")
    _save_run(db, csv, 15, "2026-01-02T00:00:00+00:00")
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == 4
        assert c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 2
    changes = run_sql_file("price_changes.sql", db)
    assert len(changes) == 1
    assert changes.iloc[0]["old_price"] == 10 and changes.iloc[0]["new_price"] == 15
    assert changes.iloc[0]["change_pct"] == 50.0


def test_every_sql_file_runs(tmp_path):
    db, csv = tmp_path / "p.db", tmp_path / "p.csv"
    _save_run(db, csv, 10, "2026-01-01T00:00:00+00:00")
    files = sorted(p.name for p in SQL_DIR.glob("*.sql"))
    assert len(files) >= 4
    for name in files:
        assert isinstance(run_sql_file(name, db), pd.DataFrame)


def test_quality_report_counts_rejected_rows():
    df = clean_products([row(), row(price="bad", product_url="https://example.test/z")])
    rep = quality_report(2, df)
    assert rep["raw_rows"] == 2 and rep["valid_rows"] == 1 and rep["rejected_rows"] == 1
    assert rep["rejected_pct"] == 50.0 and "s" in rep["by_source"]
