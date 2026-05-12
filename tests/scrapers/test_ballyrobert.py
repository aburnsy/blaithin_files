"""Regression tests for the Ballyrobert Gardens scraper."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.ballyrobert import BallyrobertScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products():
    return json.loads((CASSETTES / "ballyrobert_products.json").read_text(encoding="utf-8"))["products"]


def test_parse_record_returns_dict():
    """First product's first variant should parse into a valid record."""
    scraper = BallyrobertScraper()
    products = _products()
    record = scraper.parse_record(
        products[0], products[0]["variants"][0], "https://www.ballyrobertgardens.com/products.json"
    )
    assert record is not None
    assert record["source"] == "ballyrobert"
    assert record["product_name_raw"]
    assert isinstance(record["price_native"], float)
    assert record["price_native"] > 0
    assert record["currency"] == "GBP"
    assert record["product_url"].startswith("https://www.ballyrobertgardens.com/products/")


def test_parse_record_drops_when_price_missing():
    scraper = BallyrobertScraper()
    product = {"handle": "x", "title": "X", "body_html": "", "images": []}
    variant = {"title": "Default Title", "price": None, "available": True}
    assert scraper.parse_record(product, variant, "https://example.com") is None


def test_all_records_have_required_fields():
    scraper = BallyrobertScraper()
    products = _products()
    n = 0
    for p in products:
        for v in p["variants"]:
            rec = scraper.parse_record(p, v, "https://www.ballyrobertgardens.com/products.json")
            if rec is None:
                continue
            assert rec["source"] == "ballyrobert"
            assert rec["product_url"]
            assert rec["product_name_raw"]
            assert rec["currency"] == "GBP"
            assert isinstance(rec["price_native"], float)
            n += 1
    assert n > 0
