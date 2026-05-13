"""Regression tests for the David Austin Roses (EU) scraper."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.david_austin import DavidAustinScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products() -> list[dict]:
    return json.loads(
        (CASSETTES / "david_austin_products.json").read_text(encoding="utf-8")
    )["products"]


def test_parse_record_returns_dict():
    scraper = DavidAustinScraper()
    products = _products()
    record = scraper.parse_record(
        products[0],
        products[0]["variants"][0],
        "https://eu.davidaustinroses.com/products.json",
    )
    assert record is not None
    assert record["source"] == "david_austin"
    assert record["currency"] == "EUR"
    assert record["product_url"].startswith("https://eu.davidaustinroses.com/products/")
    assert record["product_name_raw"]


def test_all_records_have_required_fields():
    scraper = DavidAustinScraper()
    n = 0
    for p in _products():
        for v in p["variants"]:
            rec = scraper.parse_record(
                p, v, "https://eu.davidaustinroses.com/products.json"
            )
            if rec is None:
                continue
            assert rec["product_url"]
            assert rec["product_name_raw"]
            assert isinstance(rec["price_native"], float)
            n += 1
    assert n > 0


def test_parse_record_drops_when_price_missing():
    scraper = DavidAustinScraper()
    product = {"handle": "x", "title": "X", "body_html": "", "images": []}
    variant = {"title": "Default Title", "price": None, "available": True}
    assert scraper.parse_record(product, variant, "https://example.com") is None
