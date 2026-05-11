"""Regression tests for hedgingie (Hedging.ie) scraper."""

from pathlib import Path

from src.scrapers.hedgingie import HedgingIeScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def test_parse_listing_returns_urls():
    """Listing HTML should yield at least one product URL on hedging.ie."""
    scraper = HedgingIeScraper()
    html = (CASSETTES / "hedgingie_listing.html").read_text(encoding="utf-8")
    urls = scraper.parse_listing(html)
    assert len(urls) > 0
    assert all(u.startswith("https://hedging.ie/product/") for u in urls)


def test_parse_product_returns_record():
    """Product HTML should parse into a valid dict with required fields."""
    scraper = HedgingIeScraper()
    html = (CASSETTES / "hedgingie_product.html").read_text(encoding="utf-8")
    record = scraper.parse_product(
        html,
        product_url="https://hedging.ie/product/alder-trees/",
        source_url="https://hedging.ie/product-category/hedges/",
        category="Hedges",
    )
    assert record is not None
    assert record["source"] == "hedgingie"
    assert "product_name_raw" in record
    assert record["product_name_raw"]  # non-empty
    assert record["price_native"] is not None
    assert isinstance(record["price_native"], float)
    assert record["currency"] == "EUR"


def test_parse_product_returns_none_on_garbage():
    """Garbage HTML must return None, never raise."""
    scraper = HedgingIeScraper()
    record = scraper.parse_product(
        "<html><body>not a product page</body></html>",
        product_url="https://hedging.ie/product/garbage",
        source_url="https://hedging.ie/product-category/hedges/",
        category="Hedges",
    )
    assert record is None
