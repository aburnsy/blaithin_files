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


def test_save_is_atomic_no_tmp_left_behind(tmp_overrides):
    """save_overrides should leave no .tmp file behind after success."""
    save_overrides([
        MatchOverride(product_name_clean="rosa rugosa", rhs_id=1, source="llm"),
    ])
    tmp = tmp_overrides.with_suffix(".parquet.tmp")
    assert not tmp.exists(), f"stale temp file present: {tmp}"
    assert tmp_overrides.exists()


def test_save_does_not_corrupt_on_crash(tmp_overrides, monkeypatch):
    """If write_parquet raises mid-save, the live file is untouched."""
    save_overrides([
        MatchOverride(product_name_clean="original", rhs_id=42, source="llm"),
    ])

    # Sabotage the next write_parquet call
    import polars as pl
    original_write = pl.DataFrame.write_parquet

    def boom(self, *args, **kwargs):
        raise RuntimeError("disk full")
    monkeypatch.setattr(pl.DataFrame, "write_parquet", boom)

    with pytest.raises(RuntimeError):
        save_overrides([
            MatchOverride(product_name_clean="new", rhs_id=99, source="llm"),
        ])

    # Restore and reload — original must still be there
    monkeypatch.setattr(pl.DataFrame, "write_parquet", original_write)
    loaded = load_overrides()
    assert len(loaded) == 1
    assert loaded[0].product_name_clean == "original"
    assert loaded[0].rhs_id == 42
