"""CSV and SQLite storage.

* ``products`` table / products.csv  - latest snapshot (replaced each run)
* ``price_history`` table            - one row per product per run (appended, never replaced)
"""
from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
CSV_PATH = DATA_DIR / "products.csv"
DB_PATH = DATA_DIR / "products.db"

HISTORY_COLUMNS = ["scraped_at_utc", "source", "product_url", "title", "price", "currency"]


def save_outputs(df: pd.DataFrame, csv_path: Path = CSV_PATH, db_path: Path = DB_PATH) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with sqlite3.connect(db_path) as connection:
        df.to_sql("products", connection, if_exists="replace", index=False)
        df[HISTORY_COLUMNS].to_sql("price_history", connection, if_exists="append", index=False)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_product ON price_history (source, product_url, scraped_at_utc)"
        )


def load_products(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path, keep_default_na=False, na_values=[""], dtype={"category": "string", "sku": "string"})


def run_sql_file(name: str, db_path: Path = DB_PATH, sql_dir: Path = SQL_DIR) -> pd.DataFrame:
    """Run one of the queries in sql/ and return the result."""
    if not db_path.exists():
        return pd.DataFrame()
    query = (sql_dir / name).read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as connection:
        return pd.read_sql_query(query, connection)
