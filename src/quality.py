"""Data-quality report produced after every run."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPORT_PATH = Path(__file__).resolve().parents[1] / "data" / "quality_report.json"


def quality_report(raw_rows: int, df: pd.DataFrame) -> dict:
    """Summarise how much was collected, rejected and left incomplete."""
    by_source = {}
    for source, part in df.groupby("source"):
        by_source[source] = {
            "rows": int(len(part)),
            "currency": ", ".join(sorted(part["currency"].astype(str).unique())),
            "price_min": float(part["price"].min()),
            "price_max": float(part["price"].max()),
            "missing_category_pct": round(float((part["category"].astype(str) == "").mean() * 100), 1),
            "missing_rating_pct": round(float(part["rating"].isna().mean() * 100), 1),
        }
    return {
        "generated_at_utc": str(df["scraped_at_utc"].max()),
        "raw_rows": int(raw_rows),
        "valid_rows": int(len(df)),
        "rejected_rows": int(raw_rows - len(df)),
        "rejected_pct": round((raw_rows - len(df)) / raw_rows * 100, 1) if raw_rows else 0.0,
        "by_source": by_source,
    }


def save_report(report: dict, path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def load_report(path: Path = REPORT_PATH) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
