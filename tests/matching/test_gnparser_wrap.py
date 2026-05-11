"""Tests for the gnparser wrapper."""

import pytest

from src.matching.gnparser_wrap import ParseFailed, parse


def test_parse_simple_binomial():
    p = parse("Acer palmatum")
    assert p.genus == "Acer"
    assert p.species == "palmatum"
    assert p.cultivar is None


def test_parse_with_cultivar():
    p = parse("Acer palmatum 'Bloodgood'")
    assert p.genus == "Acer"
    assert p.species == "palmatum"
    assert p.cultivar == "Bloodgood"


def test_parse_with_cultivar_group():
    p = parse("Acer palmatum 'Bloodgood' (Atropurpureum Group)")
    assert p.cultivar == "Bloodgood"
    assert p.cultivar_group == "Atropurpureum Group"


def test_parse_with_authority_stripped():
    # Authority "L." (Linnaeus) should be ignored in our wrapper output
    p = parse("Lavandula angustifolia L.")
    assert p.genus == "Lavandula"
    assert p.species == "angustifolia"


def test_parse_genus_only_fails():
    with pytest.raises(ParseFailed):
        parse("Acer")


def test_parse_garbage_fails():
    with pytest.raises(ParseFailed):
        parse("not a plant name at all")


def test_parse_preserves_raw():
    p = parse("Acer palmatum 'Bloodgood'")
    assert p.raw == "Acer palmatum 'Bloodgood'"
