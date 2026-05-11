"""Regression tests for the David Austin Roses (EU) scraper.

Fixtures: tests/fixtures/cassettes/david_austin_listing.html
          tests/fixtures/cassettes/david_austin_product.html

Both captured from https://eu.davidaustinroses.com — the .eu domain is the
only one that ships to Ireland.
"""

from pathlib import Path

import pytest

from src.scrapers.david_austin import DavidAustinScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def test_parse_listing_returns_urls():
    """Listing HTML should yield at least one rose product URL, no gift cards."""
    scraper = DavidAustinScraper()
    html = (CASSETTES / "david_austin_listing.html").read_text(encoding="utf-8")
    urls = scraper.parse_listing(html)
    assert len(urls) > 0
    assert all(u.startswith("https://eu.davidaustinroses.com/products/") for u in urls)
    assert not any("gift-card" in u for u in urls)


def test_parse_product_returns_record():
    """Product HTML should parse into a valid dict with required fields."""
    scraper = DavidAustinScraper()
    html = (CASSETTES / "david_austin_product.html").read_text(encoding="utf-8")
    record = scraper.parse_product(
        html,
        product_url="https://eu.davidaustinroses.com/products/dannahue",
        source_url="https://eu.davidaustinroses.com/collections/english-roses",
        category="English Roses",
    )
    assert record is not None
    assert record["source"] == "david_austin"
    assert "product_name_raw" in record
    assert record["product_name_raw"]  # non-empty
    assert record["price_native"] is not None
    assert isinstance(record["price_native"], float)
    assert record["price_native"] > 0
    assert record["currency"] == "EUR"


def test_parse_product_returns_none_on_garbage():
    """Garbage HTML must return None, never raise."""
    scraper = DavidAustinScraper()
    record = scraper.parse_product(
        "<html><body>not a product page</body></html>",
        product_url="https://eu.davidaustinroses.com/products/garbage",
        source_url="https://eu.davidaustinroses.com/collections/english-roses",
        category="English Roses",
    )
    assert record is None
