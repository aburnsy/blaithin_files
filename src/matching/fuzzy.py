"""Bulk fuzzy residual matching via ``pl-fuzzy-frame-match`` (Jaro-Winkler).

Replaces a per-row ``rapidfuzz.process.extractOne`` loop with a single
DataFrame-level call that uses approximate nearest-neighbour blocking
(``polars-simed``) under the hood. Empirically ~90× faster on the production
140k-row corpus while producing the same matches at the chosen threshold.

The match method is still labelled ``"rapidfuzz"`` in the output schema so the
existing ``match_method`` literal (and any historical matched parquets) stay
valid — the library swap is internal.
"""

from __future__ import annotations

import logging

import polars as pl
from pl_fuzzy_frame_match import FuzzyMapping, fuzzy_match_dfs

from src.matching.models import MatchResult

DEFAULT_THRESHOLD = 0.90  # Jaro-Winkler; expressed on the natural 0..1 scale
LLM_CANDIDATE_THRESHOLD = 0.70  # wider net for the LLM top-K shortlist
LLM_CANDIDATE_K = 10
_SCORE_COL = "name_vs_ref_jaro_winkler"
_PLFF_LOGGER = logging.getLogger("matching.fuzzy.plff")
_PLFF_LOGGER.setLevel(logging.WARNING)  # keep its chatty INFO out of our logs


def _build_rhs_haystack(rhs_df: pl.DataFrame) -> pl.LazyFrame:
    """Return a lazy frame of (rhs_id, ref) with both botanical and common names lowercased."""
    id_col = "rhs_id" if "rhs_id" in rhs_df.columns else "id"
    return (
        pl.concat(
            [
                rhs_df.select(
                    pl.col(id_col).alias("rhs_id"),
                    pl.col("botanical_name").str.to_lowercase().alias("ref"),
                ),
                rhs_df.select(
                    pl.col(id_col).alias("rhs_id"),
                    pl.col("common_name").str.to_lowercase().alias("ref"),
                ),
            ],
            how="vertical",
        )
        .filter(pl.col("ref").is_not_null())
        .lazy()
    )


def bulk_fuzzy_lookup(
    clean_names: list[str],
    rhs_df: pl.DataFrame,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, MatchResult]:
    """Return ``{clean_name_lower: MatchResult}`` for names with a match ≥ threshold.

    Args:
        clean_names: cleaned product names to match. Caller may pass duplicates;
            they are deduped internally before the bulk call.
        rhs_df: the RHS DataFrame (must have ``botanical_name``, ``common_name``,
            and either ``rhs_id`` or ``id``).
        threshold: minimum Jaro-Winkler similarity in the [0, 1] range. Defaults
            to 0.90.

    Names with no candidate above ``threshold`` are absent from the returned
    dict. Lookups should be keyed on the lowercased clean name.
    """

    if not clean_names:
        return {}

    unique_names = sorted({n.lower() for n in clean_names if n})
    if not unique_names:
        return {}

    rhs_lf = _build_rhs_haystack(rhs_df)
    left_lf = pl.DataFrame({"name": unique_names}).lazy()

    matched = fuzzy_match_dfs(
        left_df=left_lf,
        right_df=rhs_lf,
        fuzzy_maps=[
            FuzzyMapping(
                left_col="name",
                right_col="ref",
                threshold_score=threshold * 100.0,
                fuzzy_type="jaro_winkler",
            )
        ],
        logger=_PLFF_LOGGER,
    )

    if matched.height == 0:
        return {}

    best = (
        matched.sort(_SCORE_COL, descending=True)
        .group_by("name", maintain_order=True)
        .first()
    )

    out: dict[str, MatchResult] = {}
    for row in best.iter_rows(named=True):
        out[row["name"]] = MatchResult(
            rhs_id=row["rhs_id"],
            method="rapidfuzz",
            confidence=float(row[_SCORE_COL]),
        )
    return out


def top_k_candidates_per_query(
    clean_names: list[str],
    rhs_df: pl.DataFrame,
    *,
    k: int = LLM_CANDIDATE_K,
    threshold: float = LLM_CANDIDATE_THRESHOLD,
) -> dict[str, list[int]]:
    """Return ``{clean_name_lower: [rhs_id, ...]}`` with up to ``k`` candidates each.

    Designed to build a tight per-batch candidate set for the LLM fallback so the
    prompt stays in the KB range instead of MB. Uses a wider threshold than
    :func:`bulk_fuzzy_lookup` (default 0.70 vs 0.90) so the LLM gets to see
    near-misses it might still resolve.

    The output is deduped per rhs_id — if a record matches on both botanical and
    common name, it appears once per query at its highest score.

    Args:
        clean_names: cleaned product names; deduped internally; caller may pass
            duplicates.
        rhs_df: RHS DataFrame with ``botanical_name``, ``common_name``, and
            either ``rhs_id`` or ``id``.
        k: max candidates per query. Defaults to :data:`LLM_CANDIDATE_K` (10).
        threshold: minimum Jaro-Winkler score in [0, 1]. Defaults to
            :data:`LLM_CANDIDATE_THRESHOLD` (0.70).

    Returns:
        Dict keyed by lowercased clean name. Names with no candidate ≥ threshold
        are present in the dict mapped to an empty list (so the caller can
        distinguish "no candidates" from "name not in residual").
    """

    if not clean_names:
        return {}

    unique_names = sorted({n.lower() for n in clean_names if n})
    if not unique_names:
        return {}

    empty_result = {n: [] for n in unique_names}

    if rhs_df.is_empty():
        return empty_result

    rhs_lf = _build_rhs_haystack(rhs_df)
    left_lf = pl.DataFrame({"name": unique_names}).lazy()

    matched = fuzzy_match_dfs(
        left_df=left_lf,
        right_df=rhs_lf,
        fuzzy_maps=[
            FuzzyMapping(
                left_col="name",
                right_col="ref",
                threshold_score=threshold * 100.0,
                fuzzy_type="jaro_winkler",
            )
        ],
        logger=_PLFF_LOGGER,
    )

    if matched.height == 0:
        return empty_result

    # Dedupe by (name, rhs_id) keeping the best score per record, then take top-K per name.
    per_record_best = matched.group_by(["name", "rhs_id"]).agg(
        pl.col(_SCORE_COL).max().alias("score")
    )
    ranked = (
        per_record_best.sort(["name", "score"], descending=[False, True])
        .group_by("name", maintain_order=False)
        .agg(pl.col("rhs_id").head(k).alias("rhs_ids"))
    )

    out = dict(empty_result)
    for row in ranked.iter_rows(named=True):
        out[row["name"]] = list(row["rhs_ids"])
    return out
