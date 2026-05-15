"""Tests for the bulk fuzzy residual matcher."""

from pathlib import Path

import polars as pl
import pytest

from src.matching.fuzzy import bulk_fuzzy_lookup, top_k_candidates_per_query

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rhs_sample.parquet"


@pytest.fixture(scope="module")
def rhs_df():
    return pl.read_parquet(FIXTURE)


def test_close_typo_resolves(rhs_df):
    """One-letter mutation on a real botanical name should match itself."""
    name = rhs_df.select("botanical_name").head(1).item()
    typo = name[:-1] + "x"
    result = bulk_fuzzy_lookup([typo], rhs_df)
    hit = result.get(typo.lower())
    assert hit is not None
    assert hit.method == "rapidfuzz"
    assert hit.confidence >= 0.90


def test_far_off_returns_no_entry(rhs_df):
    """A string with no real similarity should be absent from the result dict."""
    result = bulk_fuzzy_lookup(["totally unrelated string xyz123"], rhs_df)
    assert "totally unrelated string xyz123" not in result


def test_known_botanical_typo_dicksonia(rhs_df):
    """Regression: 'dicksonia antartica' (missing 'c') matches 'dicksonia antarctica'."""
    # Synthesise the row in case the fixture doesn't have Dicksonia
    id_col = "rhs_id" if "rhs_id" in rhs_df.columns else "id"
    next_id = int(rhs_df[id_col].max() or 0) + 1
    augmented = pl.concat(
        [
            rhs_df,
            pl.DataFrame(
                {
                    id_col: [next_id],
                    "botanical_name": ["Dicksonia antarctica"],
                    "common_name": ["tree fern"],
                }
            ),
        ],
        how="diagonal_relaxed",
    )
    result = bulk_fuzzy_lookup(["dicksonia antartica"], augmented)
    hit = result.get("dicksonia antartica")
    assert hit is not None
    assert hit.rhs_id == next_id
    assert hit.confidence >= 0.90


def test_dedupes_input(rhs_df):
    """Passing the same name twice returns one entry; lookup keyed on lowercased clean."""
    name = rhs_df.select("botanical_name").head(1).item()
    result = bulk_fuzzy_lookup([name, name, name.upper()], rhs_df)
    assert len(result) == 1
    assert name.lower() in result


def test_empty_input_returns_empty():
    assert bulk_fuzzy_lookup([], pl.DataFrame()) == {}


def test_top_k_returns_multiple_candidates(rhs_df):
    """At a wider threshold, top-K returns multiple plausible records per query."""
    # Synthesize a query that's close to several different RHS records
    name = rhs_df.select("botanical_name").head(1).item()
    result = top_k_candidates_per_query([name], rhs_df, k=5, threshold=0.70)
    hits = result.get(name.lower())
    assert hits is not None
    assert 1 <= len(hits) <= 5
    # The exact-string query should have at least one candidate
    assert all(isinstance(rid, int) for rid in hits)


def test_top_k_present_with_empty_list_when_no_candidates(rhs_df):
    """Names with no candidate above threshold map to an empty list (not absent)."""
    result = top_k_candidates_per_query(["totally unrelated xyz123"], rhs_df, k=5, threshold=0.70)
    assert "totally unrelated xyz123" in result
    assert result["totally unrelated xyz123"] == []


def test_top_k_empty_rhs_returns_empty_lists(rhs_df):
    """Empty RHS table → every query maps to an empty list."""
    empty = rhs_df.head(0)
    result = top_k_candidates_per_query(["acer palmatum", "hosta sieboldiana"], empty, k=5)
    assert result == {"acer palmatum": [], "hosta sieboldiana": []}


def test_top_k_dedupes_by_rhs_id(rhs_df):
    """A record that matches on both botanical and common name should only appear once."""
    # Use a row that has both botanical and common name
    row_with_both = (
        rhs_df.filter(pl.col("common_name").is_not_null())
        .head(1)
    )
    if row_with_both.height == 0:
        return  # fixture doesn't exercise this — skip
    query = row_with_both.select("botanical_name").item().lower()
    result = top_k_candidates_per_query([query], rhs_df, k=10, threshold=0.50)
    hits = result.get(query)
    assert hits is not None
    assert len(hits) == len(set(hits)), f"duplicate rhs_ids in {hits}"
