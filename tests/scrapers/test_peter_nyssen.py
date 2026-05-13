"""Parse-only regression tests for the Peter Nyssen scraper.

The scraper itself drives undetected_chromedriver which we never invoke
in tests — these tests only exercise the HTML extraction layer against
a saved listing-page cassette.
"""

from __future__ import annotations

from pathlib import Path

from src.scrapers.peter_nyssen import (
    _extract_cards,
    _has_next_page,
    _price_from_text,
)

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _load_listing() -> str:
    return (CASSETTES / "peter_nyssen_listing.html").read_text(encoding="utf-8")


def test_extract_cards_finds_products():
    cards = _extract_cards(_load_listing())
    # /spring-planting/dahlia-tubers/decorative-dahlias.html shows 32 per page.
    assert len(cards) >= 20


def test_extract_cards_have_required_fields():
    cards = _extract_cards(_load_listing())
    for card in cards:
        assert card["product_name"]
        assert card["product_url"].startswith("https://www.peternyssen.com/")
        assert "?" not in card["product_url"]


def test_extract_cards_have_prices():
    cards = _extract_cards(_load_listing())
    priced = [c for c in cards if c.get("price") is not None]
    assert priced, "expected at least one card with a parsed price"
    for c in priced:
        assert isinstance(c["price"], float)
        assert c["price"] > 0


def test_extract_cards_skip_sale_overlay_image():
    """The sale-badge overlay (/amlabel/) must not be picked up as the image."""
    cards = _extract_cards(_load_listing())
    for c in cards:
        if c["img_url"]:
            assert "/amlabel/" not in c["img_url"]


def test_has_next_page_true_on_listing_with_pagination():
    assert _has_next_page(_load_listing()) is True


def test_has_next_page_false_on_empty_html():
    assert _has_next_page("<html><body></body></html>") is False


def test_price_parses_gbp_and_euro_formats():
    assert _price_from_text("£1.95") == 1.95
    assert _price_from_text("£12.99") == 12.99
    assert _price_from_text("€1,299.00") == 1299.00


def test_record_from_card_drops_invalid():
    """Cards lacking a name or URL must be dropped, not yield empty records."""
    from src.scrapers.peter_nyssen import PeterNyssenScraper

    # We can't instantiate the scraper without entering the context (driver),
    # but _record_from_card is just a thin transform — pass through staticly.
    obj = PeterNyssenScraper.__new__(PeterNyssenScraper)
    assert obj._record_from_card({"product_name": "", "product_url": "x"}, source_url="x", category="x") is None
    assert obj._record_from_card({"product_name": "x", "product_url": ""}, source_url="x", category="x") is None
