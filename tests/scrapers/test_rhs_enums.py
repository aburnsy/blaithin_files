"""Decode-table coverage checks."""

from __future__ import annotations

import pytest

from src.scrapers import rhs_enums


@pytest.mark.parametrize(
    "table",
    [
        rhs_enums.PLANT_TYPE,
        rhs_enums.SUNLIGHT,
        rhs_enums.SOIL_TYPE,
        rhs_enums.ASPECT,
        rhs_enums.MOISTURE,
        rhs_enums.PH,
        rhs_enums.EXPOSURE,
        rhs_enums.FOLIAGE,
        rhs_enums.HABIT,
        rhs_enums.HARDINESS,
    ],
)
def test_decode_list_handles_full_range(table):
    """Every int in the table decodes to a non-empty string label."""
    out = rhs_enums.decode_list(list(table), table)
    assert len(out) == len(table)
    assert all(isinstance(s, str) and s for s in out)


def test_decode_list_drops_unknown_ints():
    assert rhs_enums.decode_list([999, 1, 2], rhs_enums.SUNLIGHT) == ["Full sun", "Partial shade"]


def test_decode_list_handles_none_and_empty():
    assert rhs_enums.decode_list(None, rhs_enums.SUNLIGHT) == []
    assert rhs_enums.decode_list([], rhs_enums.SUNLIGHT) == []


def test_decode_scalar_known_and_unknown():
    assert rhs_enums.decode_scalar(7, rhs_enums.HARDINESS) == "H6"
    assert rhs_enums.decode_scalar(None, rhs_enums.HARDINESS) is None
    assert rhs_enums.decode_scalar(999, rhs_enums.HARDINESS) is None


def test_plant_type_mapping_alias_for_back_compat():
    """rhs_urls.py imports PLANT_TYPE as plant_type_mapping; make sure the alias path works."""
    from src.scrapers.rhs_urls import plant_type_mapping

    assert plant_type_mapping is rhs_enums.PLANT_TYPE
    assert plant_type_mapping[6] == "Shrubs"
