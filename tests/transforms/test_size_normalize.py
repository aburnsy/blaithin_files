"""Tests for the size_normalize pipeline step.

Tests the pure parsing function on realistic size strings drawn from
data/*/data.parquet. Tests for the DataFrame-level transform separately.
"""

import polars as pl
import pytest

from src.transforms.size_normalize import (
    SizeKind,
    add_size_columns,
    parse_size,
)


# --- parse_size ----------------------------------------------------------------


@pytest.mark.parametrize("size_str,is_plant,expected_kind,expected_litres", [
    # Non-plant short-circuits before any string match.
    ("2 Litre", False, "non_plant", None),
    ("", False, "non_plant", None),
    # Bare root and rootball go categorical.
    ("Bare Root", True, "bare_root", None),
    ("bare root", True, "bare_root", None),
    ("Rootball", True, "rootball", None),
    ("Rootball + Pot", True, "rootball", None),
    # Litre values, exact and ranges.
    ("2 Litre", True, "potted", 2.0),
    ("2L", True, "potted", 2.0),
    ("2.5 ltr", True, "potted", 2.5),
    ("7.5-10 Litre", True, "potted", 7.5),
    ("10-15 Litre", True, "potted", 10.0),
    ("30-35 Litre", True, "potted", 30.0),
    # Pot codes.
    ("P9", True, "potted", 1.0),       # 9cm -> 1L per CM_TO_LITRES
    ("P11", True, "potted", 1.0),
    ("P15", True, "potted", 2.0),
    ("P25", True, "potted", 10.0),
    # cm values.
    ("9cm", True, "potted", 1.0),
    ("9 cm", True, "potted", 1.0),
    ("9.5cm", True, "potted", 1.0),    # rounds half-up to 10cm = 1L
    ("15cm", True, "potted", 2.0),
    # Out of range cm -> unknown.
    ("5cm", True, "unknown", None),
    ("60cm", True, "unknown", None),
    # Unmatched / vague.
    ("Half Standard", True, "unknown", None),
    ("in cont.", True, "unknown", None),
    ("Tree", True, "unknown", None),
    ("", True, "unknown", None),
    (None, True, "unknown", None),
])
def test_parse_size(size_str, is_plant, expected_kind, expected_litres):
    kind, litres = parse_size(size_str, is_plant=is_plant)
    assert kind == expected_kind
    assert litres == expected_litres


# --- DataFrame-level transform ------------------------------------------------


def test_add_size_columns_adds_two_new_columns():
    df = pl.DataFrame({
        "size": ["2 Litre", "Bare Root", None, "P15"],
        "is_plant": [True, True, True, True],
        "other_col": [1, 2, 3, 4],
    })
    out = add_size_columns(df)
    assert "pot_size_litres" in out.columns
    assert "size_kind" in out.columns
    assert out["pot_size_litres"].to_list() == [2.0, None, None, 2.0]
    assert out["size_kind"].to_list() == ["potted", "bare_root", "unknown", "potted"]
    # Other columns preserved.
    assert "other_col" in out.columns


def test_add_size_columns_non_plants_get_non_plant_kind():
    df = pl.DataFrame({
        "size": ["10 Litre", "Compost"],
        "is_plant": [True, False],
    })
    out = add_size_columns(df)
    assert out["size_kind"].to_list() == ["potted", "non_plant"]
    assert out["pot_size_litres"].to_list() == [10.0, None]
