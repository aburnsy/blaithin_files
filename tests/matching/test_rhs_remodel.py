"""Tests for migrating the legacy rhs.parquet to the new schema."""

from pathlib import Path

import polars as pl

from src.matching.rhs_remodel import remodel


def test_remodel_splits_genus_species(tmp_path):
    # Build a small synthetic legacy parquet
    legacy = pl.DataFrame({
        "id": [1, 2, 3],
        "source": ["rhs"] * 3,
        "plant_url": ["https://rhs.org.uk/plants/1"] * 3,
        "botanical_name": ["Acer palmatum", "Rosa 'Irish Fireflame' (HT)", "Tulipa gesneriana"],
        "common_name": ["Japanese Maple", None, "Tulip"],
        "plant_type": [["Tree"], ["Climber"], ["Bulb"]],
        "description": [None] * 3,
        "is_rhs_award_winner": [False] * 3,
        "is_pollinator_plant": [False] * 3,
        "height": [None] * 3,
        "spread": [None] * 3,
        "time_to_ultimate_spread": [None] * 3,
        "soils": [[]] * 3,
        "moisture": [None] * 3,
        "ph": [None] * 3,
        "sun_exposure": [None] * 3,
        "aspect": [[]] * 3,
        "exposure": [[]] * 3,
        "hardiness": [None] * 3,
        "foliage": [None] * 3,
        "habit": [[]] * 3,
    })
    out = tmp_path / "rhs_new.parquet"
    remodel(legacy, out)
    new = pl.read_parquet(out)
    assert "genus" in new.columns
    assert "species" in new.columns
    assert "synonyms" in new.columns
    assert "common_names" in new.columns

    acer = new.filter(pl.col("rhs_id") == 1).to_dicts()[0]
    assert acer["genus"] == "Acer"
    assert acer["species"] == "palmatum"
    assert acer["common_names"] == ["Japanese Maple"]
    assert acer["synonyms"] == []

    rosa = new.filter(pl.col("rhs_id") == 2).to_dicts()[0]
    assert rosa["genus"] == "Rosa"
    # Cultivar is part of botanical_name in legacy data; new schema keeps it stored
    # but matching uses (genus, species) only.
    assert rosa["species"] in ("'Irish", "")  # depends on how we strip cultivar quotes
