"""Regression tests for the Caragh Nurseries scraper (WooCommerce Store API)."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.carragh import CaraghScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products() -> list[dict]:
    return json.loads(
        (CASSETTES / "carragh_products.json").read_text(encoding="utf-8")
    )


def test_parse_record_returns_dict():
    scraper = CaraghScraper()
    rec = scraper.parse_record(
        _products()[0], "https://caraghnurseries.ie/wp-json/wc/store/v1/products"
    )
    assert rec is not None
    assert rec["source"] == "carragh"
    assert rec["currency"] == "EUR"
    assert rec["product_url"].startswith("https://caraghnurseries.ie")


def test_all_records_have_required_fields():
    scraper = CaraghScraper()
    n = 0
    for p in _products():
        rec = scraper.parse_record(
            p, "https://caraghnurseries.ie/wp-json/wc/store/v1/products"
        )
        if rec is None:
            continue
        assert rec["product_url"]
        assert rec["product_name_raw"]
        assert isinstance(rec["price_native"], float)
        n += 1
    assert n > 0
