"""Regression tests for the Brown Envelope Seeds scraper."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.brown_envelope import BrownEnvelopeScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products():
    return json.loads(
        (CASSETTES / "brown_envelope_products.json").read_text(encoding="utf-8")
    )["products"]


def test_parse_record_returns_dict():
    scraper = BrownEnvelopeScraper()
    products = _products()
    record = scraper.parse_record(
        products[0],
        products[0]["variants"][0],
        "https://brownenvelopeseeds.ie/products.json",
    )
    assert record is not None
    assert record["source"] == "brown_envelope"
    assert record["currency"] == "EUR"
    assert record["product_url"].startswith("https://brownenvelopeseeds.ie/products/")


def test_all_records_have_required_fields():
    scraper = BrownEnvelopeScraper()
    products = _products()
    n = 0
    for p in products:
        for v in p["variants"]:
            rec = scraper.parse_record(
                p, v, "https://brownenvelopeseeds.ie/products.json"
            )
            if rec is None:
                continue
            assert rec["product_url"]
            assert rec["product_name_raw"]
            assert isinstance(rec["price_native"], float)
            n += 1
    assert n > 0
