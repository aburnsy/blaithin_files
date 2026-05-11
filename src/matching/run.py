"""Run the deterministic match pipeline over a products DataFrame."""

from __future__ import annotations

import polars as pl

from src.matching.classify import classify_product
from src.matching.exact import RhsIndex, exact_match
from src.matching.fuzzy import build_candidates, fuzzy_match
from src.matching.gnparser_wrap import ParseFailed, parse
from src.matching.models import MatchOverride
from src.matching.normalize import clean_product_name


def run_matching(
    products_df: pl.DataFrame,
    rhs_df: pl.DataFrame,
    overrides: list[MatchOverride],
) -> pl.DataFrame:
    """Apply the deterministic match pipeline. Returns a DataFrame with match columns added.

    LLM fallback is NOT invoked here — that's Phase D's `llm.batch_resolve` which is
    called separately on the residual where match_method == "unmatched".
    """

    rhs_index = RhsIndex.from_dataframe(rhs_df)
    candidates = build_candidates(rhs_df)
    overrides_by_clean = {o.product_name_clean: o for o in overrides}

    out_rows = []
    for row in products_df.iter_rows(named=True):
        raw = row["product_name_raw"]
        clean = clean_product_name(raw)

        # Step 0: override cache wins
        if (override := overrides_by_clean.get(clean)) is not None:
            out_rows.append({
                **row,
                "product_name_clean": clean,
                "rhs_id": override.rhs_id,
                "cultivar": override.cultivar,
                "match_method": "manual_override" if override.source == "manual" else "llm",
                "match_confidence": 1.0 if override.source == "manual" else 0.95,
                "is_plant": override.is_plant,
                "product_category": override.product_category,
                "genus": None,
                "species": None,
                "cultivar_group": None,
            })
            continue

        # Step 1: parse
        try:
            parsed = parse(clean)
        except ParseFailed:
            parsed = None

        # Step 2: classify (works with or without parse)
        is_plant, category = classify_product(raw, parsed)

        # Step 3: exact match if parsed
        result = exact_match(parsed, rhs_index) if parsed is not None else None

        # Step 4: fuzzy fallback — also runs when parse failed so that
        # genus-only+cultivar names (e.g. "Galanthus 'Ding Dong'") can still
        # be matched; if fuzzy succeeds we promote is_plant to True.
        if result is None:
            fuzzy_result = fuzzy_match(clean, candidates, threshold=0.85)
            if fuzzy_result is not None:
                result = fuzzy_result
                if not is_plant:
                    # A successful fuzzy match against the RHS confirms this is a plant
                    is_plant = True
                    category = "plant"

        out_rows.append({
            **row,
            "product_name_clean": clean,
            "rhs_id": result.rhs_id if result else None,
            "cultivar": parsed.cultivar if parsed else None,
            "cultivar_group": parsed.cultivar_group if parsed else None,
            "genus": parsed.genus if parsed else None,
            "species": parsed.species if parsed else None,
            "match_method": result.method if result else "unmatched",
            "match_confidence": result.confidence if result else 0.0,
            "is_plant": is_plant,
            "product_category": category,
        })

    return pl.DataFrame(out_rows)
