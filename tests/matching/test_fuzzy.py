"""Tests for fuzzy residual matcher."""

from pathlib import Path

import polars as pl
import pytest

from src.matching.fuzzy import build_candidates, fuzzy_match

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rhs_sample.parquet"


@pytest.fixture(scope="module")
def candidates():
    df = pl.read_parquet(FIXTURE)
    return build_candidates(df)


def test_fuzzy_close_typo_resolves(candidates):
    # Take a real botanical_name from the fixture, mutate one letter, expect a match
    df = pl.read_parquet(FIXTURE)
    name = df.select("botanical_name").head(1).item()
    typo = name[:-1] + "x"  # mutate last char
    result = fuzzy_match(typo, candidates, threshold=0.85)
    assert result is not None
    assert result.method == "rapidfuzz"
    assert result.confidence >= 0.85


def test_fuzzy_far_off_returns_none(candidates):
    result = fuzzy_match("totally unrelated string xyz123", candidates, threshold=0.85)
    assert result is None
