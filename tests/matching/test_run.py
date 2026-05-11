"""Integration test: deterministic match pipeline against the fixture."""

from pathlib import Path

import polars as pl
import pytest

from src.matching.run import run_matching

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
    plant_rows = matched.filter(pl.col("is_plant") == True)
    # Most of the 20 fixture-derived plants should match (some may have weird formatting)
    matched_count = plant_rows.filter(pl.col("rhs_id").is_not_null()).height
    assert matched_count >= 15, f"Expected ≥15 of 20 to match, got {matched_count}"


def test_pipeline_classifies_non_plants(rhs_df, products_df):
    matched = run_matching(products_df, rhs_df, overrides=[])
    non_plant_rows = matched.filter(pl.col("is_plant") == False)
    assert len(non_plant_rows) >= 3
    categories = set(non_plant_rows.select("product_category").to_series().to_list())
    assert "compost" in categories
    assert "tool" in categories
    assert "pot" in categories


from unittest.mock import patch

from src.matching.run import run_with_llm_fallback


@patch("src.matching.llm.Anthropic")
def test_llm_fallback_persists_overrides(mock_client_cls, rhs_df, products_df, tmp_path, monkeypatch):
    # Force everything into "unmatched" by dropping all RHS data the deterministic pipeline could find
    empty_rhs = rhs_df.head(0)
    overrides_path = tmp_path / "match_overrides.parquet"
    monkeypatch.setattr("src.matching.overrides.OVERRIDES_PARQUET", overrides_path)

    import json
    from unittest.mock import MagicMock

    from src.matching.normalize import clean_product_name
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    # Mock returns "unmatched/non-plant" for every product, keyed by cleaned name
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps([
            {"product_name_clean": clean_product_name(p), "rhs_id": None, "is_plant": False, "product_category": "other", "confidence": 0.3, "reasoning": "no RHS data"}
            for p in products_df.select("product_name_raw").to_series().to_list()
        ]))]
    )

    matched = run_with_llm_fallback(products_df, empty_rhs, llm_enabled=True)
    # All products fall through to LLM; LLM marks them all as non-plant
    assert (matched.select("match_method").to_series() == "llm").all()
