"""Regression tests for the Plant Store scraper."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.plant_store import PlantStoreScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products():
    return json.loads(
        (CASSETTES / "plant_store_products.json").read_text(encoding="utf-8")
    )["products"]


def test_parse_record_returns_dict():
    scraper = PlantStoreScraper()
    products = _products()
    rec = scraper.parse_record(
        products[0], products[0]["variants"][0], "https://www.plantstore.ie/products.json"
    )
    assert rec is not None
    assert rec["source"] == "plant_store"
    assert rec["currency"] == "EUR"
    assert rec["product_url"].startswith("https://www.plantstore.ie/products/")


def test_all_records_have_required_fields():
    scraper = PlantStoreScraper()
    n = 0
    for p in _products():
        for v in p["variants"]:
            rec = scraper.parse_record(p, v, "https://www.plantstore.ie/products.json")
            if rec is None:
                continue
            assert rec["product_url"]
            assert rec["product_name_raw"]
            assert isinstance(rec["price_native"], float)
            n += 1
    assert n > 0
