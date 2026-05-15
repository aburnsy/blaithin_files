"""Prototype: pl-fuzzy-frame-match vs current rapidfuzz on the real corpus.

Not wired into production. Run with `.venv/Scripts/python.exe scripts/bench_pl_fuzzy.py`.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import polars as pl  # noqa: E402
from pl_fuzzy_frame_match import FuzzyMapping, fuzzy_match_dfs  # noqa: E402
from rapidfuzz import process  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

from src.matching.exact import RhsIndex, exact_match  # noqa: E402
from src.matching.gnparser_wrap import ParseFailed, parse  # noqa: E402
from src.matching.normalize import clean_product_name  # noqa: E402


def build_candidates(rhs_df: pl.DataFrame) -> list[tuple[str, int]]:
    """Inline copy of the pre-pl-fuzzy-frame-match helper so this script
    stays runnable for regression checks without depending on the old API."""
    id_col = "rhs_id" if "rhs_id" in rhs_df.columns else "id"
    out: list[tuple[str, int]] = []
    for row in rhs_df.iter_rows(named=True):
        rid = row[id_col]
        bn = row.get("botanical_name")
        cn = row.get("common_name")
        if bn:
            out.append((bn.lower(), rid))
        if cn:
            out.append((cn.lower(), rid))
    return out

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bench")


def load_all_products() -> pl.DataFrame:
    frames = []
    for d in sorted(Path("data").glob("*/")):
        if d.name in {"rhs", "rhs_urls"}:
            continue
        p = d / "data.parquet"
        if not p.exists():
            continue
        df = pl.read_parquet(p)
        if "product_name" in df.columns and "product_name_raw" not in df.columns:
            df = df.rename({"product_name": "product_name_raw"})
        frames.append(df.select("product_name_raw").with_columns(pl.lit(d.name).alias("source")))
    return pl.concat(frames, how="vertical_relaxed")


def main() -> None:
    log.info("loading products + RHS")
    products = load_all_products()
    rhs = pl.read_parquet("data/rhs/data.parquet")
    log.info(f"products: {products.height}, rhs: {rhs.height}")

    log.info("normalising + parsing products")
    t0 = time.monotonic()
    cleaned = [clean_product_name(n) for n in products["product_name_raw"].to_list()]
    parsed_list = []
    for c in cleaned:
        try:
            parsed_list.append(parse(c))
        except ParseFailed:
            parsed_list.append(None)
    log.info(f"normalise+parse: {time.monotonic() - t0:.1f}s")

    log.info("building exact-match index")
    idx = RhsIndex.from_dataframe(rhs)

    log.info("identifying rows that fall through to fuzzy")
    t0 = time.monotonic()
    fuzzy_needed: list[int] = []
    for i, parsed in enumerate(parsed_list):
        if parsed is None or exact_match(parsed, idx) is None:
            fuzzy_needed.append(i)
    log.info(
        f"fuzzy residual: {len(fuzzy_needed)}/{len(parsed_list)} "
        f"({100 * len(fuzzy_needed) / len(parsed_list):.1f}%) "
        f"({time.monotonic() - t0:.1f}s)"
    )

    cleaned_for_fuzzy = [cleaned[i].lower() for i in fuzzy_needed]

    # Plant-likely subsample: keep queries whose parse succeeded (genus + species)
    plant_likely = [i for i in fuzzy_needed if parsed_list[i] is not None]
    log.info(
        f"plant-likely (parsed but missed exact): {len(plant_likely)} "
        f"({100 * len(plant_likely) / len(fuzzy_needed):.1f}% of residual)"
    )

    # ---- A) Current rapidfuzz approach (subsample only — extrapolation is unbearable for full) ----
    log.info("building rapidfuzz candidate list")
    candidates = build_candidates(rhs)
    haystack = [c[0] for c in candidates]
    log.info(f"rapidfuzz haystack: {len(haystack)}")

    SAMPLE = 1000
    # Plant-heavy sample so quality comparison is meaningful
    sample_indices = plant_likely[:SAMPLE]
    sample_clean = [cleaned[i].lower() for i in sample_indices]
    log.info(f"running rapidfuzz on {SAMPLE} plant-likely sample queries...")
    t0 = time.monotonic()
    rapidfuzz_hits = 0
    rapidfuzz_results: list[tuple[str, int | None, float]] = []
    for n in sample_clean:
        best = process.extractOne(
            n, haystack, scorer=Levenshtein.normalized_similarity, score_cutoff=0.85
        )
        if best is None:
            rapidfuzz_results.append((n, None, 0.0))
        else:
            score = best[1]
            idx_in_h = best[2]
            rapidfuzz_results.append((n, candidates[idx_in_h][1], float(score)))
            rapidfuzz_hits += 1
    rapidfuzz_elapsed = time.monotonic() - t0
    log.info(
        f"rapidfuzz: {SAMPLE} queries in {rapidfuzz_elapsed:.1f}s "
        f"({rapidfuzz_elapsed / SAMPLE * 1000:.1f} ms/query, {rapidfuzz_hits} hits @ ≥0.85)"
    )
    extrapolated_full = rapidfuzz_elapsed / SAMPLE * len(fuzzy_needed)
    log.info(
        f"rapidfuzz extrapolated full corpus ({len(fuzzy_needed)} queries): "
        f"{extrapolated_full:.0f}s ({extrapolated_full / 60:.1f} min)"
    )

    # ---- B) pl-fuzzy-frame-match: same sample ----
    log.info(f"running pl-fuzzy-frame-match on {SAMPLE} sample queries (levenshtein @ 85)...")
    id_col = "rhs_id" if "rhs_id" in rhs.columns else "id"
    # Parity with rapidfuzz's build_candidates: both botanical AND common names
    rhs_lf = (
        pl.concat(
            [
                rhs.select(
                    pl.col(id_col).alias("rhs_id"),
                    pl.col("botanical_name").str.to_lowercase().alias("ref"),
                ),
                rhs.select(
                    pl.col(id_col).alias("rhs_id"),
                    pl.col("common_name").str.to_lowercase().alias("ref"),
                ),
            ],
            how="vertical",
        )
        .filter(pl.col("ref").is_not_null())
        .lazy()
    )
    left_sample_lf = pl.DataFrame({"q_idx": list(range(SAMPLE)), "name": sample_clean}).lazy()

    t0 = time.monotonic()
    matched_sample = fuzzy_match_dfs(
        left_df=left_sample_lf,
        right_df=rhs_lf,
        fuzzy_maps=[
            FuzzyMapping(
                left_col="name", right_col="ref", threshold_score=85.0, fuzzy_type="levenshtein"
            )
        ],
        logger=log,
    )
    plff_sample_elapsed = time.monotonic() - t0
    log.info(
        f"pl-fuzzy-frame-match sample: {matched_sample.height} match rows in "
        f"{plff_sample_elapsed:.1f}s ({plff_sample_elapsed / SAMPLE * 1000:.1f} ms/query)"
    )
    log.info(f"sample output columns: {matched_sample.columns}")

    # ---- C) pl-fuzzy-frame-match: full residual ----
    log.info(f"running pl-fuzzy-frame-match on FULL {len(fuzzy_needed)} residual...")
    left_full_lf = pl.DataFrame(
        {"q_idx": list(range(len(cleaned_for_fuzzy))), "name": cleaned_for_fuzzy}
    ).lazy()
    t0 = time.monotonic()
    matched_full = fuzzy_match_dfs(
        left_df=left_full_lf,
        right_df=rhs_lf,
        fuzzy_maps=[
            FuzzyMapping(
                left_col="name", right_col="ref", threshold_score=85.0, fuzzy_type="levenshtein"
            )
        ],
        logger=log,
    )
    plff_full_elapsed = time.monotonic() - t0
    distinct_matched_queries = matched_full.select(pl.col("q_idx").n_unique()).item()
    log.info(
        f"pl-fuzzy-frame-match full: {matched_full.height} match rows, "
        f"{distinct_matched_queries} distinct queries matched, in {plff_full_elapsed:.1f}s"
    )

    # ---- D) Quality spot-check: same 20 sample queries through current vs new ----
    log.info("\n=== QUALITY SPOT CHECK (first 20 sample queries) ===")
    score_candidates = [c for c in matched_sample.columns if c not in {"q_idx", "name", "rhs_id", "ref"}]
    log.info(f"non-key columns in output: {score_candidates}")
    plff_score_col = score_candidates[-1] if score_candidates else None
    log.info(f"using score column: {plff_score_col}")
    if plff_score_col is None:
        log.warning("no score column found; skipping per-row quality table")
        plff_lookup = {}
    else:
        plff_by_q = (
            matched_sample.sort(plff_score_col, descending=True)
            .group_by("q_idx", maintain_order=True)
            .first()
        )
        plff_lookup = {row["q_idx"]: row for row in plff_by_q.iter_rows(named=True)}

    # Only rows where AT LEAST ONE matched (interesting cases)
    print()
    header = f"{'query':<50}  {'rapidfuzz':<55}  {'plff':<55}"
    print(header)
    print("-" * len(header))
    rcount = 0
    pcount = 0
    both = 0
    only_r = 0
    only_p = 0
    rows_printed = 0
    for i in range(len(rapidfuzz_results)):
        q, rid, rscore = rapidfuzz_results[i]
        plff_row = plff_lookup.get(i, {}) if plff_lookup else {}
        plff_match = plff_row.get("ref")
        rhit = rid is not None
        phit = plff_match is not None
        if rhit:
            rcount += 1
        if phit:
            pcount += 1
        if rhit and phit:
            both += 1
        elif rhit:
            only_r += 1
        elif phit:
            only_p += 1
        if (rhit or phit) and rows_printed < 40:
            rmatch = next((h for h, c in candidates if c == rid), None) if rid else None
            plff_score = plff_row.get(plff_score_col) if plff_score_col else None
            rcell = f"{rmatch[:47]} ({rscore:.2f})" if rmatch else "-"
            pcell = f"{plff_match[:47]} ({plff_score})" if plff_match else "-"
            print(f"{q[:50]:<50}  {rcell:<55}  {pcell:<55}")
            rows_printed += 1

    print()
    log.info(
        f"on {SAMPLE} plant-likely sample: "
        f"rapidfuzz_hits={rcount} plff_hits={pcount} both={both} only_rapidfuzz={only_r} only_plff={only_p}"
    )

    # ---- E) Summary ----
    print()
    log.info("=== SUMMARY ===")
    log.info(f"corpus: {products.height} products, {rhs.height} RHS rows")
    log.info(f"fuzzy residual after exact: {len(fuzzy_needed)}")
    log.info(f"rapidfuzz (current): extrapolated {extrapolated_full / 60:.1f} min full corpus")
    log.info(f"pl-fuzzy-frame-match: actual {plff_full_elapsed:.1f}s full corpus")
    if plff_full_elapsed > 0:
        log.info(f"speedup: {extrapolated_full / plff_full_elapsed:.1f}x")


if __name__ == "__main__":
    main()
