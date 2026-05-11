"""Fuzzy residual matcher (rapidfuzz Levenshtein) over RHS botanical+synonym+common."""

from __future__ import annotations

import polars as pl
from rapidfuzz import process
from rapidfuzz.distance import Levenshtein

from src.matching.models import MatchResult


def build_candidates(rhs_df: pl.DataFrame) -> list[tuple[str, int]]:
    """Build a list of (lookup_string, rhs_id) tuples covering all RHS name variants.

    Accepts either `rhs_id` (new schema) or `id` (legacy production parquet
    before Task 16 migration runs).
    """

    id_col = "rhs_id" if "rhs_id" in rhs_df.columns else "id"

    candidates: list[tuple[str, int]] = []
    for row in rhs_df.iter_rows(named=True):
        rhs_id = row[id_col]
        botanical = row.get("botanical_name")
        common = row.get("common_name")
        if botanical:
            candidates.append((botanical.lower(), rhs_id))
        if common:
            candidates.append((common.lower(), rhs_id))
        # Synonyms[] integration in Phase E
    return candidates


def fuzzy_match(
    name: str, candidates: list[tuple[str, int]], threshold: float = 0.85
) -> MatchResult | None:
    """Best fuzzy match over candidates above `threshold`. None if no match."""

    if not candidates:
        return None

    haystack = [c[0] for c in candidates]
    best = process.extractOne(
        name.lower(),
        haystack,
        scorer=Levenshtein.normalized_similarity,
        score_cutoff=threshold,
    )
    if best is None:
        return None

    matched_str, score, idx = best
    rhs_id = candidates[idx][1]
    return MatchResult(rhs_id=rhs_id, method="rapidfuzz", confidence=float(score))
