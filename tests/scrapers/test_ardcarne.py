"""Parse-only regression tests for the Ardcarne scraper."""

from __future__ import annotations

from pathlib import Path

from src.scrapers.ardcarne import ArdcarneScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def test_parse_listing_extracts_product_urls():
    scraper = ArdcarneScraper()
    xml = (CASSETTES / "ardcarne_sitemap.xml").read_text(encoding="utf-8")
    urls = scraper.parse_listing(xml)
    assert urls == [
        "https://www.ardcarne.ie/product/32049/geranium-st-ola-5l-pot",
        "https://www.ardcarne.ie/product/5154/lavender-munstead-strain",
        "https://www.ardcarne.ie/product/37380/juniperus-repanda-3l-pot",
    ]


def test_parse_listing_strips_query_and_dedupes():
    """The /products/ listing URLs and duplicate entries must be excluded."""
    scraper = ArdcarneScraper()
    xml = (CASSETTES / "ardcarne_sitemap.xml").read_text(encoding="utf-8")
    urls = scraper.parse_listing(xml)
    assert all("/product/" in u for u in urls)
    assert all("/products/" not in u for u in urls)
    assert all("?" not in u for u in urls)
    assert len(urls) == len(set(urls))


def test_parse_product_returns_record():
    scraper = ArdcarneScraper()
    html = (CASSETTES / "ardcarne_product.html").read_text(encoding="utf-8")
    record = scraper.parse_product(
        html,
        product_url="https://www.ardcarne.ie/product/32049/geranium-st-ola-5l-pot",
        source_url="https://www.ardcarne.ie/sitemap.xml",
        category="sitemap",
    )
    assert isinstance(record, dict)
    assert record["source"] == "ardcarne"
    assert record["product_name"].startswith("Geranium")
    assert record["price"] == 11.99
    assert record["category"] == "Summer Nectar"
    assert record["stock"] == 1
    assert record["img_url"]


def test_parse_product_returns_none_when_unpriced():
    scraper = ArdcarneScraper()
    html = "<html><body><h1>Some Plant</h1></body></html>"
    record = scraper.parse_product(
        html,
        product_url="https://www.ardcarne.ie/product/0/some-plant",
        source_url="https://www.ardcarne.ie/sitemap.xml",
        category="sitemap",
    )
    assert record is None


def test_discover_categories_returns_sitemap_seed():
    scraper = ArdcarneScraper()
    seeds = scraper.discover_categories()
    assert seeds == [("https://www.ardcarne.ie/sitemap.xml", "sitemap")]
