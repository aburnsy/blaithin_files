"""Integration test: deterministic match pipeline against the fixture."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

from src.matching.models import MatchOverride
from src.matching.run import (
    _augment_with_parent_species,
    _species_level_index_by_genus,
    run_matching,
    run_with_llm_fallback,
)

RHS_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rhs_sample.parquet"


@pytest.fixture
def rhs_df():
    return pl.read_parquet(RHS_FIXTURE)


@pytest.fixture
def products_df(rhs_df):
    """Build a small product DataFrame from the RHS fixture, plus some non-plants."""
    plants = rhs_df.head(20).select(
        pl.lit("test_nursery").alias("source"),
        pl.lit("https://example.com/p").alias("product_url"),
        pl.col("botanical_name").alias("product_name_raw"),
        pl.lit(9.99).alias("price_native"),
        pl.lit("EUR").alias("currency"),
    )
    non_plants = pl.DataFrame({
        "source": ["test_nursery"] * 3,
        "product_url": ["https://example.com/n"] * 3,
        "product_name_raw": ["Multipurpose Compost 50L", "Felco Secateurs", "Terracotta pot 30cm"],
        "price_native": [12.0, 49.0, 8.50],
        "currency": ["EUR"] * 3,
    })
    return pl.concat([plants, non_plants])


def test_pipeline_matches_known_plants(rhs_df, products_df):
    matched = run_matching(products_df, rhs_df, overrides=[])
    plant_rows = matched.filter(pl.col("is_plant").eq(True))
    # Most of the 20 fixture-derived plants should match (some may have weird formatting)
    matched_count = plant_rows.filter(pl.col("rhs_id").is_not_null()).height
    assert matched_count >= 15, f"Expected ≥15 of 20 to match, got {matched_count}"


def test_pipeline_classifies_non_plants(rhs_df, products_df):
    matched = run_matching(products_df, rhs_df, overrides=[])
    non_plant_rows = matched.filter(pl.col("is_plant").eq(False))
    assert len(non_plant_rows) >= 3
    categories = set(non_plant_rows.select("product_category").to_series().to_list())
    assert "compost" in categories
    assert "tool" in categories
    assert "pot" in categories


@patch("src.matching.llm._invoke_claude")
def test_llm_fallback_persists_overrides(mock_invoke, rhs_df, products_df, tmp_path, monkeypatch):
    # Force everything into "unmatched" by dropping all RHS data the deterministic pipeline could find
    empty_rhs = rhs_df.head(0)
    overrides_path = tmp_path / "match_overrides.parquet"
    # The audit dir is derived from OVERRIDES_PARQUET.parent in src.matching.overrides
    audit_dir = tmp_path / "llm_audit"
    monkeypatch.setattr("src.matching.overrides.OVERRIDES_PARQUET", overrides_path)

    import json

    from src.matching.normalize import clean_product_name

    # Mock returns "unmatched/non-plant" for every product, keyed by cleaned name
    mock_invoke.return_value = json.dumps([
        {"product_name_clean": clean_product_name(p), "rhs_id": None, "is_plant": False, "product_category": "other", "confidence": 0.3, "reasoning": "no RHS data"}
        for p in products_df.select("product_name_raw").to_series().to_list()
    ])

    matched = run_with_llm_fallback(products_df, empty_rhs, llm_enabled=True)
    # All products fall through to LLM; LLM marks them all as non-plant
    assert (matched.select("match_method").to_series() == "llm").all()

    # Audit JSONL was written with one line per resolved override
    audit_files = list(audit_dir.glob("resolutions_*.jsonl"))
    assert len(audit_files) == 1, f"expected exactly one audit file, got {audit_files}"
    lines = audit_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == products_df.height
    parsed = [json.loads(line) for line in lines]
    assert all(p["source"] == "llm" for p in parsed)


def test_species_level_index_picks_only_bare_binomials(rhs_df):
    """Species-level index must exclude cultivar/parenthetical/subspecies rows."""
    idx = _species_level_index_by_genus(rhs_df)
    # Every collected rhs_id must point to a botanical_name of the shape
    # "Genus species" (two tokens, no quote, no paren).
    flat_ids = {rid for ids in idx.values() for rid in ids}
    rows = rhs_df.filter(pl.col("rhs_id").is_in(list(flat_ids)))
    names = rows.select("botanical_name").to_series().to_list()
    for n in names:
        assert "'" not in n, f"cultivar leaked into species-level index: {n}"
        assert "(" not in n, f"parenthetical leaked into species-level index: {n}"
        assert len(n.split(" ")) == 2, f"non-binomial leaked into species-level index: {n}"


def test_augment_with_parent_species_prepends_parent(rhs_df):
    """Each query gets its parsed genus's species-level rhs_ids merged in at the front."""
    # Pick a genus that has a bare-binomial record in the fixture.
    idx = _species_level_index_by_genus(rhs_df)
    genus = next(iter(idx))
    parent_id = idx[genus][0]

    unmatched = pl.DataFrame({
        "product_name_clean": [f"{genus} fakecultivar"],
        "genus": [genus],
    })
    augmented = _augment_with_parent_species(
        candidates_per_name={f"{genus.lower()} fakecultivar": [999_999]},
        unmatched=unmatched,
        rhs_df=rhs_df,
        cap=15,
    )
    merged = augmented[f"{genus.lower()} fakecultivar"]
    assert parent_id in merged, "parent species rhs_id missing from augmented shortlist"
    assert merged.index(parent_id) < merged.index(999_999), (
        "parent species should come before fuzzy hits"
    )


def test_override_application_preserves_parsed_genus_species(rhs_df):
    """An override hit must still populate gnparser-derived genus/species/cultivar."""
    # Build an override for a known fixture plant. Pick the first species-level
    # rhs_id from the fixture so we have a known target.
    first_plant = rhs_df.filter(
        ~pl.col("botanical_name").str.contains("'")
        & (pl.col("botanical_name").str.split(" ").list.len() == 2)
    ).head(1).to_dicts()[0]
    botanical_name = first_plant["botanical_name"]

    # Add a product row that this override should hit.
    one_product = pl.DataFrame({
        "source": ["test_nursery"],
        "product_url": ["https://example.com/o"],
        "product_name_raw": [f"{botanical_name} 'NewCultivar' 50cm"],
        "price_native": [12.5],
        "currency": ["EUR"],
    })

    from src.matching.normalize import clean_product_name
    override = MatchOverride(
        product_name_clean=clean_product_name(f"{botanical_name} 'NewCultivar' 50cm"),
        rhs_id=first_plant["rhs_id"],
        cultivar="NewCultivar",
        is_plant=True,
        product_category="plant",
        source="llm",
        model="test-model",
        created_at=datetime.now(UTC),
        notes="test",
    )

    matched = run_matching(one_product, rhs_df, overrides=[override])
    row = matched.to_dicts()[0]
    expected_genus = botanical_name.split(" ")[0]
    expected_species = botanical_name.split(" ")[1]
    assert row["genus"] == expected_genus, f"genus nuked on override apply: {row}"
    assert row["species"] == expected_species, f"species nuked on override apply: {row}"
    assert row["rhs_id"] == first_plant["rhs_id"]
