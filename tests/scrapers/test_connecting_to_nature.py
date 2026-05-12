"""Regression tests for the Connecting to Nature scraper."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.connecting_to_nature import ConnectingToNatureScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products():
    return json.loads(
        (CASSETTES / "connecting_to_nature_products.json").read_text(encoding="utf-8")
    )["products"]


def test_parse_record_returns_dict():
    scraper = ConnectingToNatureScraper()
    products = _products()
    record = scraper.parse_record(
        products[0],
        products[0]["variants"][0],
        "https://connectingtonature.ie/products.json",
    )
    assert record is not None
    assert record["source"] == "connecting_to_nature"
    assert record["currency"] == "EUR"
    assert record["product_url"].startswith("https://connectingtonature.ie/products/")


def test_all_records_have_required_fields():
    scraper = ConnectingToNatureScraper()
    n = 0
    for p in _products():
        for v in p["variants"]:
            rec = scraper.parse_record(p, v, "https://connectingtonature.ie/products.json")
            if rec is None:
                continue
            assert rec["product_url"]
            assert rec["product_name_raw"]
            assert isinstance(rec["price_native"], float)
            n += 1
    assert n > 0
