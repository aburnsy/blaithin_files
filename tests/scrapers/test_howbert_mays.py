"""Regression tests for the Howbert & Mays scraper."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.howbert_mays import HowbertMaysScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products():
    return json.loads(
        (CASSETTES / "howbert_mays_products.json").read_text(encoding="utf-8")
    )["products"]


def test_parse_record_returns_dict():
    scraper = HowbertMaysScraper()
    products = _products()
    record = scraper.parse_record(
        products[0], products[0]["variants"][0], "https://howbertandmays.ie/products.json"
    )
    assert record is not None
    assert record["source"] == "howbert_mays"
    assert record["currency"] == "EUR"
    assert record["product_url"].startswith("https://howbertandmays.ie/products/")


def test_all_records_have_required_fields():
    scraper = HowbertMaysScraper()
    n = 0
    for p in _products():
        for v in p["variants"]:
            rec = scraper.parse_record(p, v, "https://howbertandmays.ie/products.json")
            if rec is None:
                continue
            assert rec["product_url"]
            assert rec["product_name_raw"]
            assert isinstance(rec["price_native"], float)
            n += 1
    assert n > 0
