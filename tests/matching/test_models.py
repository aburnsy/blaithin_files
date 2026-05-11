"""Tests for matching pydantic models."""

import pytest
from pydantic import ValidationError

from src.matching.models import (
    MatchOverride,
    MatchResult,
    ParsedName,
    RhsRecord,
)


def test_parsed_name_minimal():
    p = ParsedName(genus="Acer", species="palmatum")
    assert p.genus == "Acer"
    assert p.species == "palmatum"
    assert p.cultivar is None
    assert p.cultivar_group is None


def test_parsed_name_with_cultivar():
    p = ParsedName(genus="Acer", species="palmatum", cultivar="Bloodgood")
    assert p.cultivar == "Bloodgood"


def test_parsed_name_genus_only_is_invalid():
    with pytest.raises(ValidationError):
        ParsedName(genus="Acer")  # species is required


def test_match_result_method_enum():
    valid = ("url_field", "gnparser_exact", "rapidfuzz", "llm", "manual_override", "unmatched")
    for m in valid:
        r = MatchResult(rhs_id=1 if m != "unmatched" else None, method=m, confidence=0.9)
        assert r.method == m
    with pytest.raises(ValidationError):
        MatchResult(rhs_id=1, method="invalid", confidence=0.9)


def test_match_result_unmatched_allows_null_rhs_id():
    r = MatchResult(rhs_id=None, method="unmatched", confidence=0.0)
    assert r.rhs_id is None


def test_rhs_record_synonyms_default_empty():
    r = RhsRecord(rhs_id=42, genus="Acer", species="palmatum", botanical_name="Acer palmatum")
    assert r.synonyms == []
    assert r.common_names == []


def test_match_override_round_trip_dict():
    o = MatchOverride(
        product_name_clean="acer palmatum bloodgood",
        rhs_id=42,
        cultivar="Bloodgood",
        is_plant=True,
        product_category="plant",
        source="llm",
        model="claude-haiku-4-5",
    )
    d = o.model_dump()
    o2 = MatchOverride.model_validate(d)
    assert o == o2
