"""Tests for the deterministic non-plant prefilter."""

import pytest

from src.matching.classify import classify_product
from src.matching.models import ParsedName


def test_classifies_compost_as_non_plant():
    is_plant, category = classify_product("Multipurpose Compost 50L", parsed=None)
    assert is_plant is False
    assert category == "compost"


def test_classifies_secateurs_as_tool():
    is_plant, category = classify_product("Felco No.2 Secateurs", parsed=None)
    assert is_plant is False
    assert category == "tool"


def test_classifies_pot_as_pot():
    is_plant, category = classify_product("Terracotta plant pot 30cm", parsed=None)
    assert is_plant is False
    assert category == "pot"


def test_classifies_fertiliser_as_fertiliser():
    is_plant, category = classify_product("Tomato fertiliser 1L", parsed=None)
    assert is_plant is False
    assert category == "fertiliser"


def test_parsed_genus_implies_plant():
    parsed = ParsedName(genus="Acer", species="palmatum")
    is_plant, category = classify_product("Acer palmatum 9cm", parsed=parsed)
    assert is_plant is True
    assert category == "plant"


def test_tulipa_with_bulbs_indicator_is_bulb():
    parsed = ParsedName(genus="Tulipa", species="gesneriana", cultivar="Apricot Beauty")
    is_plant, category = classify_product("Tulipa 'Apricot Beauty' 5 bulbs", parsed=parsed)
    assert is_plant is True
    assert category == "bulb"


def test_unparseable_unknown_falls_to_other():
    is_plant, category = classify_product("Mystery item xyz", parsed=None)
    assert is_plant is False
    assert category == "other"
