"""Regression tests for the Mount Venus Nursery scraper."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.mount_venus import MountVenusScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products():
    return json.loads((CASSETTES / "mount_venus_products.json").read_text(encoding="utf-8"))


def test_parse_record_returns_dict():
    scraper = MountVenusScraper()
    products = _products()
    rec = scraper.parse_record(
        products[0], "https://mountvenusnursery.com/wp-json/wc/store/v1/products"
    )
    assert rec is not None
    assert rec["source"] == "mount_venus"
    assert rec["currency"] == "EUR"
    assert rec["product_url"].startswith("https://mountvenusnursery.com")


def test_all_records_have_required_fields():
    scraper = MountVenusScraper()
    n = 0
    for p in _products():
        rec = scraper.parse_record(p, "https://mountvenusnursery.com/wp-json/wc/store/v1/products")
        if rec is None:
            continue
        assert rec["product_url"]
        assert rec["product_name_raw"]
        assert isinstance(rec["price_native"], float)
        n += 1
    assert n > 0
