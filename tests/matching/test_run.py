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
