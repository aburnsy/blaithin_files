"""Run the deterministic match pipeline over a products DataFrame.

Per-row work (override cache → parse → classify → exact match) is followed by
a single bulk fuzzy call against the residual via ``src.matching.fuzzy``.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from src.common.logging import get_logger
from src.matching.classify import classify_product
from src.matching.exact import RhsIndex, exact_match
from src.matching.fuzzy import (
    DEFAULT_THRESHOLD,
    LLM_CANDIDATE_K,
    LLM_CANDIDATE_THRESHOLD,
    bulk_fuzzy_lookup,
    top_k_candidates_per_query,
)
from src.matching.gnparser_wrap import ParseFailed, parse
from src.matching.models import MatchOverride
from src.matching.normalize import clean_product_name

AUDIT_DIR = Path(__file__).resolve().parents[2] / "data" / "llm_audit"

_PROGRESS_EVERY = 5_000

log = get_logger("matching.run")


def run_matching(
    products_df: pl.DataFrame,
    rhs_df: pl.DataFrame,
    overrides: list[MatchOverride],
    *,
    phase: str = "deterministic",
) -> pl.DataFrame:
    """Apply the deterministic match pipeline. Returns a DataFrame with match columns added.

    LLM fallback is NOT invoked here — that's Phase D's `llm.batch_resolve` which is
    called separately on the residual where match_method == "unmatched".
    """

    total = len(products_df)
    log.info("deterministic_start", phase=phase, rows=total, overrides=len(overrides))

    t0 = time.monotonic()
    rhs_index = RhsIndex.from_dataframe(rhs_df)
    log.info(
        "rhs_index_built",
        phase=phase,
        rhs_rows=len(rhs_df),
        elapsed_s=round(time.monotonic() - t0, 2),
    )

    overrides_by_clean = {o.product_name_clean: o for o in overrides}

    out_rows: list[dict] = []
    pending_fuzzy: list[tuple[int, str]] = []  # (row_idx, clean_lower)

    loop_started = time.monotonic()
    last_tick = loop_started

    for i, row in enumerate(products_df.iter_rows(named=True), start=1):
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
        else:
            try:
                parsed = parse(clean)
            except ParseFailed:
                parsed = None

            is_plant, category = classify_product(raw, parsed)

            result = exact_match(parsed, rhs_index) if parsed is not None else None

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

            if result is None:
                pending_fuzzy.append((i - 1, clean.lower()))

        if i % _PROGRESS_EVERY == 0:
            now = time.monotonic()
            log.info(
                "deterministic_progress",
                phase=phase,
                done=i,
                total=total,
                pct=round(100 * i / total, 1),
                tick_s=round(now - last_tick, 1),
                elapsed_s=round(now - loop_started, 1),
            )
            last_tick = now

    log.info(
        "deterministic_done",
        phase=phase,
        rows=total,
        elapsed_s=round(time.monotonic() - loop_started, 1),
    )

    # Bulk fuzzy pass on the residual
    if pending_fuzzy:
        log.info(
            "fuzzy_bulk_start",
            phase=phase,
            residual=len(pending_fuzzy),
            threshold=DEFAULT_THRESHOLD,
        )
        t0 = time.monotonic()
        fuzzy_results = bulk_fuzzy_lookup(
            [c for _, c in pending_fuzzy],
            rhs_df,
            threshold=DEFAULT_THRESHOLD,
        )
        fuzzy_elapsed = time.monotonic() - t0
        log.info(
            "fuzzy_bulk_done",
            phase=phase,
            queries=len(pending_fuzzy),
            unique_queries=len({c for _, c in pending_fuzzy}),
            matched=len(fuzzy_results),
            elapsed_s=round(fuzzy_elapsed, 1),
        )

        for row_idx, clean_lower in pending_fuzzy:
            hit = fuzzy_results.get(clean_lower)
            if hit is None:
                continue
            row = out_rows[row_idx]
            row["rhs_id"] = hit.rhs_id
            row["match_method"] = hit.method
            row["match_confidence"] = hit.confidence
            # A successful fuzzy hit confirms this is a plant
            if not row["is_plant"]:
                row["is_plant"] = True
                row["product_category"] = "plant"

    return pl.DataFrame(out_rows, infer_schema_length=None)


def run_with_llm_fallback(
    products_df: pl.DataFrame,
    rhs_df: pl.DataFrame,
    *,
    llm_enabled: bool = True,
    api_key: str | None = None,
    llm_concurrency: int = 1,
) -> pl.DataFrame:
    """Run deterministic pipeline; LLM-resolve any residual; persist overrides; re-apply.

    This is the production entry point. The deterministic pipeline is also useful in
    isolation for fast offline test runs.
    """

    from src.matching.llm import batch_resolve
    from src.matching.overrides import load_overrides, save_overrides

    overrides = load_overrides()
    matched = run_matching(products_df, rhs_df, overrides=overrides, phase="initial")

    if not llm_enabled:
        return matched

    unmatched = matched.filter(pl.col("match_method") == "unmatched")
    residual = len(unmatched)
    if residual == 0:
        log.info("llm_skipped", reason="no_residual")
        return matched

    log.info("llm_phase_start", residual=residual)

    unmatched_names = unmatched.select("product_name_clean").to_series().to_list()

    # Build a per-product top-K shortlist so each batch's prompt only carries the
    # few candidates that could plausibly match — keeps prompts in the KB range.
    log.info(
        "llm_top_k_start",
        k=LLM_CANDIDATE_K,
        threshold=LLM_CANDIDATE_THRESHOLD,
        residual=len(unmatched_names),
    )
    t0 = time.monotonic()
    candidates_per_name = top_k_candidates_per_query(
        unmatched_names,
        rhs_df,
        k=LLM_CANDIDATE_K,
        threshold=LLM_CANDIDATE_THRESHOLD,
    )
    needed_ids: set[int] = set()
    for ids in candidates_per_name.values():
        needed_ids.update(ids)
    avg_k = round(
        sum(len(v) for v in candidates_per_name.values()) / max(1, len(candidates_per_name)),
        1,
    )
    log.info(
        "llm_top_k_done",
        elapsed_s=round(time.monotonic() - t0, 1),
        unique_candidates=len(needed_ids),
        avg_per_query=avg_k,
    )

    # Build sparse rhs_lookup containing only the candidate ids we'll actually send.
    id_col = "rhs_id" if "rhs_id" in rhs_df.columns else "id"
    if needed_ids:
        subset = rhs_df.filter(pl.col(id_col).is_in(list(needed_ids)))
    else:
        subset = rhs_df.head(0)
    rhs_lookup = {
        row[id_col]: {
            "genus": (row["botanical_name"] or "").split(" ")[0] if row["botanical_name"] else "",
            "species": (row["botanical_name"] or "").split(" ")[1].strip("'\"") if row["botanical_name"] and " " in row["botanical_name"] else "",
            "common_names": [row["common_name"]] if row.get("common_name") else [],
            "synonyms": row.get("synonyms") or [],
        }
        for row in subset.iter_rows(named=True)
    }
    log.info("llm_rhs_lookup_built", count=len(rhs_lookup))

    # Audit log: append-only JSONL, one line per resolved override. Survives a
    # corrupted parquet — the cache can be rebuilt from these files if needed.
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = AUDIT_DIR / f"resolutions_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    log.info("llm_audit_log", path=str(audit_path))

    # Running snapshot of every override (existing + newly resolved). We rewrite
    # the parquet atomically after every batch so a crash never loses more than
    # the batch in flight at the moment.
    running_overrides = list(overrides)

    def _persist_batch(batch_overrides: list[MatchOverride]) -> None:
        with audit_path.open("a", encoding="utf-8") as f:
            for ov in batch_overrides:
                f.write(json.dumps(ov.model_dump(mode="json"), default=str) + "\n")
        running_overrides.extend(batch_overrides)
        save_overrides(running_overrides)

    t0 = time.monotonic()
    new_overrides = batch_resolve(
        unmatched_names,
        candidates_per_name,
        rhs_lookup,
        api_key=api_key,
        on_batch_complete=_persist_batch,
        concurrency=llm_concurrency,
    )
    log.info(
        "llm_phase_done",
        new_overrides=len(new_overrides),
        elapsed_s=round(time.monotonic() - t0, 1),
    )

    # Final state save (idempotent — the callback already wrote each batch).
    save_overrides(overrides + new_overrides)

    # Re-run the deterministic pipeline so the new overrides flow through
    return run_matching(
        products_df, rhs_df, overrides=overrides + new_overrides, phase="post_llm"
    )
