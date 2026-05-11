"""Round-trip tests for match_overrides.parquet read/write."""


import pytest

from src.matching.models import MatchOverride
from src.matching.overrides import (
    load_overrides,
    save_overrides,
    upsert_override,
)


@pytest.fixture
def tmp_overrides(tmp_path, monkeypatch):
    p = tmp_path / "match_overrides.parquet"
    monkeypatch.setattr("src.matching.overrides.OVERRIDES_PARQUET", p)
    return p


def test_load_empty_returns_empty_list(tmp_overrides):
    save_overrides([])
    assert load_overrides() == []


def test_round_trip_one(tmp_overrides):
    o = MatchOverride(
        product_name_clean="acer palmatum bloodgood",
        rhs_id=98765,
        cultivar="Bloodgood",
        is_plant=True,
        product_category="plant",
        source="llm",
        model="claude-haiku-4-5",
    )
    save_overrides([o])
    loaded = load_overrides()
    assert len(loaded) == 1
    assert loaded[0].product_name_clean == "acer palmatum bloodgood"
    assert loaded[0].rhs_id == 98765
    assert loaded[0].cultivar == "Bloodgood"


def test_upsert_replaces_existing(tmp_overrides):
    save_overrides([
        MatchOverride(
            product_name_clean="acer palmatum bloodgood",
            rhs_id=1,
            source="llm",
        )
    ])
    upsert_override(MatchOverride(
        product_name_clean="acer palmatum bloodgood",
        rhs_id=98765,
        source="manual",
        notes="corrected by Andrew",
    ))
    loaded = load_overrides()
    assert len(loaded) == 1
    assert loaded[0].rhs_id == 98765
    assert loaded[0].source == "manual"
