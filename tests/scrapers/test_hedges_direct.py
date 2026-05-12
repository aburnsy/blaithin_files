"""Regression tests for the Hedges & Trees Direct scraper."""

from __future__ import annotations

import json
from pathlib import Path

from src.scrapers.hedges_direct import HedgesDirectScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _products():
    return json.loads((CASSETTES / "hedges_direct_products.json").read_text(encoding="utf-8"))


def test_parse_record_returns_dict():
    scraper = HedgesDirectScraper()
    rec = scraper.parse_record(
        _products()[0], "https://hedgesandtreesdirect.ie/wp-json/wc/store/v1/products"
    )
    assert rec is not None
    assert rec["source"] == "hedges_direct"
    assert rec["currency"] == "EUR"


def test_all_records_have_required_fields():
    scraper = HedgesDirectScraper()
    n = 0
    for p in _products():
        rec = scraper.parse_record(
            p, "https://hedgesandtreesdirect.ie/wp-json/wc/store/v1/products"
        )
        if rec is None:
            continue
        assert rec["product_url"]
        assert rec["product_name_raw"]
        assert isinstance(rec["price_native"], float)
        n += 1
    assert n > 0
