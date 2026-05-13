"""Regression tests for gardens4you scraper rewrite."""

from pathlib import Path

import pytest

from src.scrapers.gardens4you import Gardens4YouScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def test_parse_listing_extracts_urls_from_sitemap():
    scraper = Gardens4YouScraper()
    xml = (CASSETTES / "gardens4you_sitemap.xml").read_text(encoding="utf-8")
    urls = scraper.parse_listing(xml)
    assert len(urls) > 0
    assert all(u.startswith("https://www.gardens4you.ie") for u in urls)
    assert len(urls) == len(set(urls))
    assert all("?" not in u for u in urls)


def test_discover_categories_returns_sitemap_seed():
    scraper = Gardens4YouScraper()
    seeds = scraper.discover_categories()
    assert seeds == [("https://www.gardens4you.ie/sitemaps/ie/sitemap.xml", "")]


def test_parse_product_returns_record():
    scraper = Gardens4YouScraper()
    html = (CASSETTES / "gardens4you_product.html").read_text(encoding="utf-8")
    record = scraper.parse_product(
        html,
        product_url="https://www.gardens4you.ie/cortaderia-selloana-pampas-grass-white-a02954.html",
        source_url="https://www.gardens4you.ie/garden-plants/perennials/",
        category="Perennials",
    )
    assert record is not None
    assert record["source"] == "gardens4you"
    assert "product_name_raw" in record
    assert record["product_name_raw"]  # non-empty
    assert record["price_native"] is not None
    assert record["currency"] == "EUR"


def test_parse_product_returns_none_on_garbage():
    """Critical: legacy code raised Exception; rewrite must drop and continue."""
    scraper = Gardens4YouScraper()
    record = scraper.parse_product(
        "<html><body>not a product page</body></html>",
        product_url="https://www.gardens4you.ie/garbage",
        source_url="https://www.gardens4you.ie/",
        category="x",
    )
    assert record is None


def test_parse_product_size_is_nullable():
    """Size must be None when no size signal is present — no 'Bare Root' fallback."""
    scraper = Gardens4YouScraper()
    minimal_html = """
    <html><body>
      <h1>Some Plant With No Size Info</h1>
      <span class="price">€5.00</span>
    </body></html>
    """
    record = scraper.parse_product(
        minimal_html,
        product_url="https://www.gardens4you.ie/some-plant.html",
        source_url="https://www.gardens4you.ie/garden-plants/perennials/",
        category="Perennials",
    )
    assert record is not None
    assert record["size"] is None, f"Expected None size, got {record['size']!r}"


def test_parse_product_never_raises_on_bad_del_as():
    """Simulate the exact scenario that triggered the line-30 raise Exception.

    The legacy scraper raised Exception when the 'Delivered as' cell contained
    unexpected text. The rewrite must return None or a valid record, never raise.
    """
    scraper = Gardens4YouScraper()
    # Craft HTML that mimics what used to trigger the raise
    tricky_html = """
    <html><body>
      <h1>Mystery Bulb</h1>
      <table>
        <tr><td data-th="Delivered as" class="col data">Some weird delivery method</td></tr>
      </table>
      <span class="price">€9.99</span>
    </body></html>
    """
    # Must not raise — legacy would have raised Exception("NOT FOUND...")
    try:
        record = scraper.parse_product(
            tricky_html,
            product_url="https://www.gardens4you.ie/mystery-bulb.html",
            source_url="https://www.gardens4you.ie/",
            category="Bulbs",
        )
    except Exception as exc:
        pytest.fail(f"parse_product raised unexpectedly: {exc}")
    # Record may be a dict (product parsed successfully) or None (dropped); either is fine
    assert record is None or isinstance(record, dict)
