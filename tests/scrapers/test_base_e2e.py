"""End-to-end smoke: a fake scraper using BaseScraper + mocked httpx."""

from unittest.mock import MagicMock, patch

from src.scrapers.base import BaseScraper


class FakeScraper(BaseScraper):
    source = "fake"
    rate_limit_seconds = 0  # don't sleep in tests

    def discover_categories(self):
        return [("https://fake.example.com/cat1", "Cat1")]

    def parse_listing(self, html):
        return ["https://fake.example.com/p1", "https://fake.example.com/p2"]

    def parse_product(self, html, product_url, source_url, category):
        if "p2" in product_url:
            return None  # simulate a drop
        return {
            "source": "fake",
            "product_url": product_url,
            "product_name": "Fake plant",
            "price": 1.0,
        }


@patch("src.scrapers.http.httpx.Client.get")
def test_e2e_scrape(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200, text="<html>ok</html>", raise_for_status=lambda: None
    )
    with FakeScraper() as s:
        results = s.run()

    assert len(results) == 1  # p1 succeeded, p2 returned None
    assert s.report.products_in == 2
    assert s.report.products_parsed == 1
    assert s.report.dropped == {"parse_returned_none": 1}


class CrossCategoryScraper(BaseScraper):
    """Same product URL appears in two categories — should fetch it once."""

    source = "cross"
    rate_limit_seconds = 0

    def discover_categories(self):
        return [
            ("https://x.example.com/c1", "C1"),
            ("https://x.example.com/c2", "C2"),
        ]

    def parse_listing(self, html):
        return ["https://x.example.com/shared", "https://x.example.com/shared"]

    def parse_product(self, html, product_url, source_url, category):
        return {"source": "cross", "product_url": product_url, "category": category}


@patch("src.scrapers.http.httpx.Client.get")
def test_run_dedupes_product_urls_across_categories(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200, text="<html>ok</html>", raise_for_status=lambda: None
    )
    with CrossCategoryScraper() as s:
        results = s.run()

    # 2 categories fetched + 1 product fetched (deduped from 4 occurrences)
    assert mock_get.call_count == 3
    assert len(results) == 1
    assert s.report.products_in == 1
    assert s.report.products_parsed == 1
