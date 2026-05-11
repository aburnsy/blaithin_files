"""Tests for the BaseScraper ABC."""

from datetime import date

import pytest

from src.common.report import ScrapeReport
from src.scrapers.base import BaseScraper


def test_subclass_must_implement_methods():
    class Incomplete(BaseScraper):
        source = "incomplete"

    with pytest.raises(TypeError):
        Incomplete()


def test_complete_subclass_instantiates():
    class Complete(BaseScraper):
        source = "complete"

        def discover_categories(self):
            return [("https://example.com/cat", "Cat")]

        def parse_listing(self, html):
            return ["https://example.com/p/1"]

        def parse_product(self, html, product_url, source_url, category):
            return {"product_url": product_url, "product_name": "X", "price": 1.0}

    s = Complete()
    assert s.source == "complete"
    assert isinstance(s.report, ScrapeReport)


def test_drop_increments_report_counters():
    class Complete(BaseScraper):
        source = "complete"
        def discover_categories(self): return []
        def parse_listing(self, html): return []
        def parse_product(self, html, product_url, source_url, category): return None

    s = Complete()
    s._drop("missing_price")
    s._drop("missing_price")
    s._drop("parse_error")
    assert s.report.dropped == {"missing_price": 2, "parse_error": 1}
