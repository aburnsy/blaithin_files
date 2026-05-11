"""Tests for scraper-side ProductRecord validation helper."""

import pytest
from pydantic import ValidationError

from src.scrapers.models import RawProduct, validate_record


def test_minimal_raw_product():
    p = RawProduct(
        source="tullys",
        product_url="https://shop.tullynurseries.ie/p/1",
        product_name_raw="Acer palmatum",
        price_native=29.95,
    )
    assert p.source == "tullys"
    assert p.currency == "EUR"


def test_validate_record_accepts_minimum():
    record = {
        "source": "tullys",
        "product_url": "https://shop.tullynurseries.ie/p/1",
        "product_name_raw": "Acer palmatum",
        "price_native": 29.95,
    }
    p = validate_record(record)
    assert p.size is None  # nullable now — no fake "9 cm" defaults


def test_validate_record_rejects_missing_required():
    with pytest.raises(ValidationError):
        validate_record({"source": "tullys"})
