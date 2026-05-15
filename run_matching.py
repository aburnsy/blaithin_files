#! .venv/Scripts/python.exe

"""Run the matching pipeline over the latest per-nursery parquets + RHS data.

Writes per-nursery ``data/<nursery>/matched.parquet`` intermediates, then
concatenates them into ``data/products_matched.parquet``.

Incremental by default: a nursery is rematched only when its source parquet
or the RHS table is newer than its intermediate. ``--force`` rematches every
nursery. The deterministic + LLM pipeline runs once cross-nursery on the
changed set (preserves prompt-cache efficiency), then the result is split by
source and each portion is written to its own intermediate file.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import polars as pl

from src.common.logging import configure as configure_logging
from src.common.logging import get_logger
from src.common.nurseries import scraped_nursery_slugs

FINAL_OUTPUT = Path("data/products_matched.parquet")
RHS_PATH = Path("data/rhs/data.parquet")
INTERMEDIATE_NAME = "matched.parquet"


def _intermediate_path(nursery: str) -> Path:
    return Path(f"data/{nursery}/{INTERMEDIATE_NAME}")


def _latest_source_parquet(nursery: str) -> Path | None:
    """Newest scrape parquet for ``nursery``, ignoring the matched intermediate."""
    parquets = sorted(
        p for p in Path(f"data/{nursery}").glob("*.parquet")
        if p.name != INTERMEDIATE_NAME
    )
    return parquets[-1] if parquets else None


def _decide_changed(
    pairs: list[tuple[str, Path]],
    rhs_path: Path,
    *,
    force: bool,
) -> tuple[set[str], dict[str, str]]:
    """Pick which nurseries need rematching. Returns ``(slugs, reason_by_slug)``."""
    if force:
        return {n for n, _ in pairs}, {n: "force" for n, _ in pairs}

    changed: set[str] = set()
    reasons: dict[str, str] = {}
    rhs_mtime = rhs_path.stat().st_mtime
    for nursery, source in pairs:
        intermediate = _intermediate_path(nursery)
        if not intermediate.exists():
            changed.add(nursery)
            reasons[nursery] = "no_intermediate"
            continue
        int_mtime = intermediate.stat().st_mtime
        if source.stat().st_mtime > int_mtime:
            changed.add(nursery)
            reasons[nursery] = "source_newer"
            continue
        if rhs_mtime > int_mtime:
            changed.add(nursery)
            reasons[nursery] = "rhs_newer"
    return changed, reasons


def _load_products(pairs: list[tuple[str, Path]], log) -> pl.DataFrame:
    frames = []
    for nursery, parquet in pairs:
        df = pl.read_parquet(parquet).with_columns(pl.lit(nursery).alias("source"))
        if "product_name" in df.columns and "product_name_raw" not in df.columns:
            df = df.rename({"product_name": "product_name_raw"})
        log.info("loaded_nursery", nursery=nursery, rows=len(df), path=str(parquet))
        frames.append(df)
    return pl.concat(frames, how="diagonal_relaxed")


def _write_intermediate(nursery: str, df: pl.DataFrame, log) -> Path:
    path = _intermediate_path(nursery)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    df.write_parquet(tmp)
    os.replace(tmp, path)
    log.info("wrote_intermediate", nursery=nursery, rows=len(df), path=str(path))
    return path


def _concat_final(slugs: list[str], output: Path, log) -> bool:
    """Concat every existing intermediate into ``output``. Returns True on success."""
    frames = []
    skipped: list[str] = []
    for nursery in slugs:
        path = _intermediate_path(nursery)
        if not path.exists():
            skipped.append(nursery)
            continue
        frames.append(pl.read_parquet(path))
    if skipped:
        log.warning("concat_skipped_missing", nurseries=skipped)
    if not frames:
        log.error("no_intermediates_to_concat")
        return False
    combined = pl.concat(frames, how="diagonal_relaxed")
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".parquet.tmp")
    combined.write_parquet(tmp)
    os.replace(tmp, output)
    log.info(
        "wrote_final",
        path=str(output),
        rows=len(combined),
        nurseries=len(frames),
    )
    return True


def _final_is_current(slugs: list[str], output: Path) -> bool:
    """True if ``output`` exists and is at least as new as every intermediate."""
    if not output.exists():
        return False
    out_mtime = output.stat().st_mtime
    for nursery in slugs:
        path = _intermediate_path(nursery)
        if path.exists() and path.stat().st_mtime > out_mtime:
            return False
    return True


def _log_method_breakdown(log, df: pl.DataFrame, label: str) -> None:
    if "match_method" not in df.columns:
        return
    counts = (
        df.group_by("match_method").len().sort("len", descending=True).to_dicts()
    )
    log.info("match_method_breakdown", scope=label, counts=counts)


def main(*, force: bool, llm_concurrency: int = 1) -> int:
    configure_logging(source="matching", force=True)
    log = get_logger("matching")

    from src.matching.run import run_with_llm_fallback
    from src.transforms.size_normalize import add_size_columns

    slugs = scraped_nursery_slugs()
    pairs: list[tuple[str, Path]] = []
    for n in slugs:
        src = _latest_source_parquet(n)
        if src:
            pairs.append((n, src))

    found = {n for n, _ in pairs}
    missing = [s for s in slugs if s not in found]
    if missing:
        log.warning("nurseries_missing_data", nurseries=missing)

    if not pairs:
        log.error("no_inputs", message="no nursery parquets found — run scrapes first")
        return 1

    if not RHS_PATH.exists():
        log.error("missing_rhs", path=str(RHS_PATH))
        return 1

    ordered_slugs = [n for n, _ in pairs]
    changed, reasons = _decide_changed(pairs, RHS_PATH, force=force)

    log.info(
        "plan",
        total=len(pairs),
        changed=sorted(changed),
        unchanged=sorted(set(ordered_slugs) - changed),
        reasons=reasons,
    )

    if not changed:
        if _final_is_current(ordered_slugs, FINAL_OUTPUT):
            log.info(
                "up_to_date",
                output=str(FINAL_OUTPUT),
                message="all intermediates and final concat are current",
            )
            return 0
        log.info(
            "rebuilding_final_only",
            message="all intermediates fresh, but final concat is stale — concatenating",
        )
        return 0 if _concat_final(ordered_slugs, FINAL_OUTPUT, log) else 1

    started = time.monotonic()
    changed_pairs = [(n, p) for n, p in pairs if n in changed]

    log.info("loading_inputs_start", nurseries=len(changed_pairs))
    products_df = _load_products(changed_pairs, log)
    log.info("loading_rhs", path=str(RHS_PATH))
    rhs_df = pl.read_parquet(RHS_PATH)
    log.info(
        "inputs_loaded",
        products=len(products_df),
        rhs=len(rhs_df),
        nurseries=len(changed_pairs),
    )

    matched = run_with_llm_fallback(
        products_df, rhs_df, llm_enabled=True, llm_concurrency=llm_concurrency
    )
    _log_method_breakdown(log, matched, "rematched")

    log.info("size_normalize_start", rows=len(matched))
    size_started = time.monotonic()
    matched = add_size_columns(matched)
    log.info(
        "size_normalize_done",
        elapsed_s=round(time.monotonic() - size_started, 1),
    )

    log.info("split_and_write_intermediates_start", nurseries=len(changed_pairs))
    for nursery in [n for n, _ in changed_pairs]:
        portion = matched.filter(pl.col("source") == nursery)
        _write_intermediate(nursery, portion, log)

    log.info("concat_final_start", nurseries=len(ordered_slugs))
    ok = _concat_final(ordered_slugs, FINAL_OUTPUT, log)

    log.info("done", elapsed_s=round(time.monotonic() - started, 1))
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the matching pipeline against the latest scraped data.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-match every nursery even if its intermediate is fresh.",
    )
    parser.add_argument(
        "--llm-concurrency",
        type=int,
        default=1,
        help="Number of concurrent `claude -p` batches during LLM fallback (default 1).",
    )
    args = parser.parse_args()

    raise SystemExit(main(force=args.force, llm_concurrency=args.llm_concurrency))
