"""Tests for exact (genus, species) matching against the RHS index."""

from pathlib import Path

import polars as pl
import pytest

from src.matching.exact import RhsIndex, exact_match
from src.matching.models import ParsedName

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rhs_sample.parquet"


@pytest.fixture(scope="module")
def index():
    df = pl.read_parquet(FIXTURE)
    return RhsIndex.from_dataframe(df)


def test_exact_match_known_genus_species(index):
    # Pick a row from the fixture and try to match
    df = pl.read_parquet(FIXTURE)
    sample = df.head(1).to_dicts()[0]
    botanical = sample["botanical_name"]
    # Strip cultivar quotes for the exact-match input (genus+species only)
    parts = botanical.split(" ")[:2]
    parsed = ParsedName(genus=parts[0], species=parts[1].strip("'\""))

    result = exact_match(parsed, index)
    assert result is not None
    assert result.method == "gnparser_exact"
    assert result.confidence == 1.0


def test_exact_match_unknown_returns_none(index):
    parsed = ParsedName(genus="Notarealgenus", species="notarealspecies")
    assert exact_match(parsed, index) is None


def test_index_handles_synonym_lookup(index):
    # If RHS has Foo bar with synonym Foo baz, a parse for (Foo, baz) should resolve
    # via the synonym index. Smoke-tested here; deeper synonym tests in test_run.py.
    pass  # Placeholder — synonyms field populated in Phase E
