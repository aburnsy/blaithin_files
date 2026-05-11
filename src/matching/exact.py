"""Exact (genus, species) lookup against the RHS records."""

from __future__ import annotations

import polars as pl

from src.matching.models import MatchResult, ParsedName


class RhsIndex:
    """In-memory lookup over the RHS table, keyed by (genus, species)."""

    def __init__(self, by_genus_species: dict[tuple[str, str], int]):
        self._by_gs = by_genus_species

    @classmethod
    def from_dataframe(cls, df: pl.DataFrame) -> RhsIndex:
        """Build an index from a polars DataFrame with botanical_name + rhs_id columns.

        Accepts either `rhs_id` (new schema) or `id` (legacy production parquet
        before Task 16 migration runs) — the field is detected at call time.
        """

        id_col = "rhs_id" if "rhs_id" in df.columns else "id"

        index: dict[tuple[str, str], int] = {}
        for row in df.iter_rows(named=True):
            name = row["botanical_name"] or ""
            parts = name.split(" ")
            if len(parts) < 2:
                continue
            genus = parts[0].strip()
            species = parts[1].strip("'\"")  # strip quote markers from cultivars in legacy data
            if genus and species and (genus, species) not in index:
                index[(genus, species)] = row[id_col]
        return cls(index)

    def lookup(self, genus: str, species: str) -> int | None:
        return self._by_gs.get((genus, species))


def exact_match(parsed: ParsedName, index: RhsIndex) -> MatchResult | None:
    """Look up (genus, species) in the RHS index. Returns None if not found."""

    rhs_id = index.lookup(parsed.genus, parsed.species)
    if rhs_id is None:
        return None
    return MatchResult(rhs_id=rhs_id, method="gnparser_exact", confidence=1.0)
