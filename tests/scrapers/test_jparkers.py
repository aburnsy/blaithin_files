"""Parse-only regression tests for the J Parker's scraper."""

from __future__ import annotations

from pathlib import Path

from src.scrapers.jparkers import JParkersScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def test_listing_has_grid_true_on_listing():
    html = (CASSETTES / "jparkers_listing.html").read_text(encoding="utf-8")
    assert JParkersScraper._listing_has_grid(html) is True


def test_listing_has_grid_false_on_empty():
    assert JParkersScraper._listing_has_grid("<html><body></body></html>") is False


def test_parse_listing_returns_unique_product_urls():
    scraper = JParkersScraper()
    html = (CASSETTES / "jparkers_listing.html").read_text(encoding="utf-8")
    urls = scraper.parse_listing(html)
    assert len(urls) > 0
    assert all(u.startswith("https://www.jparkers.com/") for u in urls)
    assert len(urls) == len(set(urls))
    assert all("?" not in u for u in urls)


def test_parse_product_returns_record():
    scraper = JParkersScraper()
    html = (CASSETTES / "jparkers_product.html").read_text(encoding="utf-8")
    record = scraper.parse_product(
        html,
        product_url="https://www.jparkers.com/dahlia-rancho/",
        source_url="https://www.jparkers.com/bulbs/dahlias/dahlia-pick-mix/",
        category="Bulbs",
    )
    assert isinstance(record, dict)
    assert record["source"] == "jparkers"
    assert record["product_name"] == "Dahlia 'Rancho'"
    assert record["price"] == 6.99
    assert record["category"] == "Bulbs"
    assert record["img_url"] and record["img_url"].startswith("https://cdn11.bigcommerce.com/")
    # description from accordion section
    assert record["description"]


def test_parse_product_returns_none_on_garbage():
    scraper = JParkersScraper()
    record = scraper.parse_product(
        "<html><body>not a product page</body></html>",
        product_url="https://www.jparkers.com/garbage/",
        source_url="https://www.jparkers.com/",
        category="x",
    )
    assert record is None
