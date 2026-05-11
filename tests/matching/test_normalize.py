"""Unit tests for product name normalization."""

import json
from pathlib import Path

import pytest

from src.matching.normalize import clean_product_name

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "products_sample.json"


@pytest.mark.parametrize("case", json.loads(FIXTURE.read_text()))
def test_clean_product_name(case):
    if case["expected_clean"] is None:
        pytest.skip("expected_clean not yet annotated for this sample")
    assert clean_product_name(case["raw"]) == case["expected_clean"]


def test_clean_strips_pot_codes():
    assert clean_product_name("Acer palmatum 9cm") == "Acer palmatum"
    assert clean_product_name("Acer palmatum 2L") == "Acer palmatum"
    assert clean_product_name("Acer palmatum 3 ltr") == "Acer palmatum"
    assert clean_product_name("Acer palmatum P9") == "Acer palmatum"


def test_clean_strips_quantity_packs():
    assert clean_product_name("Tulipa 'Apricot Beauty' 5 bulbs") == "Tulipa 'Apricot Beauty'"
    assert clean_product_name("Pack of 10 Tulipa 'Apricot Beauty'") == "Tulipa 'Apricot Beauty'"


def test_clean_strips_common_name_parenthetical():
    assert clean_product_name("Hedera helix (English Ivy)") == "Hedera helix"


def test_clean_preserves_cultivar_quotes():
    assert clean_product_name("Acer palmatum 'Bloodgood'") == "Acer palmatum 'Bloodgood'"


def test_clean_handles_extra_whitespace():
    assert clean_product_name("  Acer   palmatum  ") == "Acer palmatum"
