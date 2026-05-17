"""Run the deterministic match pipeline over a products DataFrame.

Per-row work (override cache → parse → classify → exact match) is followed by
a single bulk fuzzy call against the residual via ``src.matching.fuzzy``.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

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

_PROGRESS_EVERY = 5_000

log = get_logger("matching.run")


def _species_level_index_by_genus(rhs_df: pl.DataFrame) -> dict[str, list[int]]:
    """Return ``{genus: [rhs_id, ...]}`` for species-level records only.

    "Species-level" = botanical_name has the shape ``"Genus species"`` (no
    single quote, no parenthetical, no subspecies/forma rank). These are the
    parent-species records the LLM should fall back to when a specific cultivar
    isn't catalogued.

    Older RHS parquets don't carry separate ``genus``/``species`` columns — in
    that case we derive the genus by splitting ``botanical_name`` on its first
    space, which is exactly the same heuristic the production parquet was built
    from.
    """
    id_col = "rhs_id" if "rhs_id" in rhs_df.columns else "id"

    df = rhs_df
    if "genus" not in df.columns:
        df = df.with_columns(
            pl.col("botanical_name").str.split(" ").list.get(0).alias("genus")
        )

    df = df.filter(
        pl.col("genus").is_not_null()
        & pl.col("botanical_name").is_not_null()
        & ~pl.col("botanical_name").str.contains("'")
        & ~pl.col("botanical_name").str.contains(r"\(")
        & (pl.col("botanical_name").str.split(" ").list.len() == 2)
    )

    return {
        row["genus"]: list(row["rhs_ids"])
        for row in df.group_by("genus")
        .agg(pl.col(id_col).alias("rhs_ids"))
        .iter_rows(named=True)
    }


def _augment_with_parent_species(
    *,
    candidates_per_name: dict[str, list[int]],
    unmatched: pl.DataFrame,
    rhs_df: pl.DataFrame,
    cap: int,
) -> dict[str, list[int]]:
    """Merge species-level RHS rhs_ids (by parsed genus) into each query's shortlist.

    The fuzzy shortlist is built from string similarity, which can miss the
    obvious parent species record (a "Dianthus 'I Love U'" query doesn't
    fuzzy-match "Dianthus caryophyllus" closely enough to surface it). This
    augmentation closes that gap so the LLM has the option to fall back to a
    species-level rhs_id instead of returning null.

    Parent-species ids are prepended (before the fuzzy hits) so they're the
    first thing the LLM sees; per-query list is capped at ``cap`` to keep
    prompt size bounded.
    """

    if "genus" not in unmatched.columns:
        return candidates_per_name

    species_by_genus = _species_level_index_by_genus(rhs_df)
    if not species_by_genus:
        return candidates_per_name

    genus_per_name: dict[str, str] = {}
    for row in unmatched.select("product_name_clean", "genus").iter_rows(named=True):
        genus = row["genus"]
        if genus:
            genus_per_name[row["product_name_clean"].lower()] = genus

    augmented = dict(candidates_per_name)
    for name_lower, genus in genus_per_name.items():
        existing = augmented.get(name_lower, [])
        parents = species_by_genus.get(genus, [])
        if not parents and not existing:
            continue
        merged: list[int] = []
        seen: set[int] = set()
        for rid in list(parents) + list(existing):  # parents first
            if rid in seen:
                continue
            seen.add(rid)
            merged.append(rid)
            if len(merged) >= cap:
                break
        augmented[name_lower] = merged

    return augmented


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

        # Step 0: override cache wins. Even on a hit, run the parser so the
        # gnparser-derived genus/species/cultivar_group columns get populated —
        # otherwise an LLM override with rhs_id=null leaves those fields blank
        # and the row falls out of any genus-grouped UI view.
        if (override := overrides_by_clean.get(clean)) is not None:
            try:
                parsed_override = parse(clean)
            except ParseFailed:
                parsed_override = None
            out_rows.append({
                **row,
                "product_name_clean": clean,
                "rhs_id": override.rhs_id,
                "cultivar": override.cultivar or (parsed_override.cultivar if parsed_override else None),
                "match_method": "manual_override" if override.source == "manual" else "llm",
                "match_confidence": 1.0 if override.source == "manual" else 0.95,
                "is_plant": override.is_plant,
                "product_category": override.product_category,
                "genus": parsed_override.genus if parsed_override else None,
                "species": parsed_override.species if parsed_override else None,
                "cultivar_group": parsed_override.cultivar_group if parsed_override else None,
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
    llm_backend: str = "claude",
) -> pl.DataFrame:
    """Run deterministic pipeline; LLM-resolve any residual; persist overrides; re-apply.

    This is the production entry point. The deterministic pipeline is also useful in
    isolation for fast offline test runs.

    Args:
        llm_backend: ``"claude"`` (default) shells out to ``claude -p`` against
            Claude Haiku via :mod:`src.matching.llm`. ``"local"`` routes through
            the local Ollama server (:mod:`src.matching.llm_local`). Default
            stays on Claude until the local model is A/B-validated.
    """

    if llm_backend == "local":
        from src.matching.llm_local import batch_resolve
    elif llm_backend == "claude":
        from src.matching.llm import batch_resolve
    else:
        raise ValueError(
            f"llm_backend must be 'local' or 'claude', got {llm_backend!r}"
        )
    from src.matching.overrides import (
        append_jsonl_overrides,
        load_overrides,
        new_audit_path,
        save_overrides,
    )

    overrides = load_overrides()
    matched = run_matching(products_df, rhs_df, overrides=overrides, phase="initial")

    if not llm_enabled:
        return matched

    unmatched = matched.filter(pl.col("match_method") == "unmatched")
    residual = len(unmatched)
    if residual == 0:
        log.info("llm_skipped", reason="no_residual")
        return matched

    # Dedupe by clean name: the same product (e.g. "Olea europaea") is often
    # stocked by many nurseries, so a row-level list sends the same name to the
    # LLM N times. One override applies to all rows via overrides_by_clean in
    # the post-LLM deterministic re-run.
    unmatched_names_unique = (
        unmatched.select("product_name_clean")
        .unique(maintain_order=True)
        .to_series()
        .to_list()
    )

    log.info(
        "llm_phase_start",
        residual=residual,
        unique_names=len(unmatched_names_unique),
    )

    unmatched_names = unmatched_names_unique

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

    # Augment each query's shortlist with the species-level RHS records for its
    # parsed genus. Without this, "Dianthus 'Early Love'" never sees
    # "Dianthus caryophyllus" in the shortlist (fuzzy match doesn't pick it up
    # — the cultivar string drowns out the genus). With it, the LLM has a
    # parent-species record to fall back to instead of returning rhs_id=null.
    candidates_per_name = _augment_with_parent_species(
        candidates_per_name=candidates_per_name,
        unmatched=unmatched,
        rhs_df=rhs_df,
        cap=LLM_CANDIDATE_K + 5,
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

    # Audit log: append-only JSONL, one line per resolved override. This is
    # the source of truth for "what has been resolved" — the parquet snapshot
    # is only rewritten once the run completes (see save_overrides call below).
    audit_path = new_audit_path(datetime.now(UTC))
    log.info("llm_audit_log", path=str(audit_path))

    def _persist_batch(batch_overrides: list[MatchOverride]) -> None:
        append_jsonl_overrides(audit_path, batch_overrides)

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

    # End-of-run parquet snapshot. Only reached if batch_resolve completed
    # without raising — a crash leaves the audit JSONL as the recovery record.
    save_overrides(overrides + new_overrides)

    # Re-run the deterministic pipeline so the new overrides flow through
    return run_matching(
        products_df, rhs_df, overrides=overrides + new_overrides, phase="post_llm"
    )
