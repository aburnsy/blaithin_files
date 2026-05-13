"""Parse-only regression tests for the Promesse de Fleurs scraper."""

from __future__ import annotations

from pathlib import Path

from src.scrapers.promesse import (
    PromesseScraper,
    _category_from_url,
    _extract_cards,
    _price_from_text,
)

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


def _load_listing() -> str:
    return (CASSETTES / "promesse_listing.html").read_text(encoding="utf-8")


def test_extract_cards_returns_expected_count():
    cards = _extract_cards(_load_listing())
    assert len(cards) == 49


def test_extract_cards_have_required_fields():
    for card in _extract_cards(_load_listing()):
        assert card["product_name"]
        assert card["product_url"].startswith("https://www.promessedefleurs.ie/")
        assert "?" not in card["product_url"]
        assert isinstance(card.get("price"), float) or card.get("price") is None


def test_price_parses_euro_format():
    assert _price_from_text("€0.30") == 0.30
    assert _price_from_text("€19.95") == 19.95
    assert _price_from_text("€1,299.00") == 1299.00


def test_category_from_url_uses_top_segment():
    assert _category_from_url(
        "https://www.promessedefleurs.ie/annuals/flower-seeds/cosmos-seeds.html"
    ) == "Annuals"
    assert _category_from_url(
        "https://www.promessedefleurs.ie/perennials/example.html"
    ) == "Perennials"


def test_record_from_card_returns_record():
    scraper = PromesseScraper()
    cards = _extract_cards(_load_listing())
    record = scraper._record_from_card(cards[0], source_url="https://www.promessedefleurs.ie/all-plants.html")
    assert record is not None
    assert record["source"] == "promesse"
    assert record["product_name"]
    assert record["product_url"]
    assert record["category"]


def test_record_from_card_drops_invalid():
    scraper = PromesseScraper()
    bad = {"product_name": "", "product_url": None}
    assert scraper._record_from_card(bad, source_url="x") is None
