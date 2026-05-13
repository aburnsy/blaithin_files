"""Parse-only regression tests for the Mr Middleton scraper."""

from __future__ import annotations

from pathlib import Path

from src.scrapers.mr_middleton import MrMiddletonScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def test_listing_has_grid_detects_cards():
    html = (CASSETTES / "mr_middleton_listing.html").read_text(encoding="utf-8")
    assert MrMiddletonScraper._listing_has_grid(html) is True


def test_listing_has_grid_false_on_empty():
    assert MrMiddletonScraper._listing_has_grid("<html><body></body></html>") is False


def test_parse_listing_returns_unique_product_urls():
    scraper = MrMiddletonScraper()
    html = (CASSETTES / "mr_middleton_listing.html").read_text(encoding="utf-8")
    urls = scraper.parse_listing(html)
    assert len(urls) > 0
    assert all(u.startswith("https://www.mrmiddleton.com/") for u in urls)
    assert len(urls) == len(set(urls))
    assert all("?" not in u for u in urls)


def test_parse_product_returns_record():
    scraper = MrMiddletonScraper()
    html = (CASSETTES / "mr_middleton_product.html").read_text(encoding="utf-8")
    record = scraper.parse_product(
        html,
        product_url="https://www.mrmiddleton.com/citrus-tree-summer-feed/",
        source_url="https://www.mrmiddleton.com/fruit-trees/",
        category="Fruit",
    )
    assert isinstance(record, dict)
    assert record["source"] == "mr_middleton"
    assert record["product_name"] == "Citrus Tree Summer Feed"
    assert record["price"] == 10.0
    assert record["category"] == "Fruit"
    assert record["product_url"] == "https://www.mrmiddleton.com/citrus-tree-summer-feed/"
    assert record["description"] and "fruit drop" in record["description"].lower()
    assert record["img_url"] and record["img_url"].startswith("https://cdn11.bigcommerce.com/")


def test_price_range_takes_first_price():
    """Some MM products display "€22.00 - €149.99" — must not parse as 2200149.99."""
    from bs4 import BeautifulSoup
    html = '<span class="price price--withTax">€22.00 - €149.99</span>'
    soup = BeautifulSoup(html, "html.parser")
    assert MrMiddletonScraper._extract_page_price(soup) == 22.0


def test_parse_product_returns_none_on_garbage():
    scraper = MrMiddletonScraper()
    record = scraper.parse_product(
        "<html><body>not a product page</body></html>",
        product_url="https://www.mrmiddleton.com/garbage/",
        source_url="https://www.mrmiddleton.com/",
        category="x",
    )
    assert record is None
