#! .venv/Scripts/python.exe

import argparse
import os
from pathlib import Path

import polars as pl
import pyarrow.dataset as ds

from src.common.freshness import should_scrape
from src.common.nurseries import scraped_nursery_slugs
from src.common.storage import export_data_locally
from src.scrapers import (
    arboretum,
    ballyrobert,
    beattys,
    brown_envelope,
    carragh,
    connecting_to_nature,
    david_austin,
    dutchgrown,
    fluwel,
    future_forests,
    gardens4you,
    hedgingie,
    howbert_mays,
    newlands,
    plant_store,
    plantgift,
    quickcrop,
    rhs,
    rhs_urls,
    tullys,
    windyridge,
)

# Single source of truth for "nurseries we currently scrape". Pulled from
# config/nurseries.yaml — any entry with `runs_on: github-actions`. Used for
# both the freshness gate and the matching input loop.
SCRAPED_NURSERIES: tuple[str, ...] = scraped_nursery_slugs()


def _force_from_env_or_arg(arg_force: bool) -> bool:
    if arg_force:
        return True
    raw = os.environ.get("FORCE_SCRAPE", "").strip().lower()
    return raw in ("1", "true", "yes")


def _max_age_days_from_env(default: int = 30) -> int:
    raw = os.environ.get("SCRAPE_MAX_AGE_DAYS")
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"WARN: SCRAPE_MAX_AGE_DAYS={raw!r} is not an int; using {default}")
        return default


def _run_matching(*, llm_enabled: bool) -> None:
    """Load latest per-nursery parquets + RHS, run the matching pipeline, write output."""

    from src.matching.run import run_with_llm_fallback

    frames = []
    for nursery in SCRAPED_NURSERIES:
        nursery_dir = Path(f"data/{nursery}")
        parquets = sorted(nursery_dir.glob("*.parquet"))
        if not parquets:
            print(f"No parquets for {nursery}, skipping.")
            continue
        frames.append(pl.read_parquet(parquets[-1]).with_columns(pl.lit(nursery).alias("source")))

    if not frames:
        raise SystemExit("No nursery parquets found — run scrapes first.")

    products_df = pl.concat(frames, how="diagonal_relaxed").rename(
        {"product_name": "product_name_raw"}
    )
    rhs_df = pl.read_parquet("data/rhs.parquet")

    matched = run_with_llm_fallback(products_df, rhs_df, llm_enabled=llm_enabled)
    out = Path("data/products_matched.parquet")
    matched.write_parquet(out)
    print(f"Wrote {len(matched)} matched products -> {out}")


def main(params):
    if params.site in SCRAPED_NURSERIES:
        force = _force_from_env_or_arg(params.force)
        max_age = _max_age_days_from_env()
        run, reason = should_scrape(params.site, max_age_days=max_age, force=force)
        print(reason)
        if not run:
            return

    match params.site:
        case "tullys":
            export_data_locally(
                table=tullys.get_product_data(),
            )
        case "quickcrop":
            export_data_locally(
                table=quickcrop.get_product_data(),
            )
        case "gardens4you":
            export_data_locally(
                table=gardens4you.get_product_data(),
            )
        case "carragh":
            export_data_locally(
                table=carragh.get_product_data(),
            )
        case "arboretum":
            export_data_locally(
                table=arboretum.get_product_data(),
            )
        case "hedgingie":
            export_data_locally(
                table=hedgingie.get_product_data(),
            )
        case "david_austin":
            export_data_locally(
                table=david_austin.get_product_data(),
            )
        case "ballyrobert":
            export_data_locally(
                table=ballyrobert.get_product_data(),
            )
        case "brown_envelope":
            export_data_locally(
                table=brown_envelope.get_product_data(),
            )
        case "connecting_to_nature":
            export_data_locally(
                table=connecting_to_nature.get_product_data(),
            )
        case "howbert_mays":
            export_data_locally(
                table=howbert_mays.get_product_data(),
            )
        case "newlands":
            export_data_locally(
                table=newlands.get_product_data(),
            )
        case "dutchgrown":
            export_data_locally(
                table=dutchgrown.get_product_data(),
            )
        case "fluwel":
            export_data_locally(
                table=fluwel.get_product_data(),
            )
        case "plantgift":
            export_data_locally(
                table=plantgift.get_product_data(),
            )
        case "future_forests":
            export_data_locally(
                table=future_forests.get_product_data(),
            )
        case "windyridge":
            export_data_locally(
                table=windyridge.get_product_data(),
            )
        case "beattys":
            export_data_locally(
                table=beattys.get_product_data(),
            )
        case "plant_store":
            export_data_locally(
                table=plant_store.get_product_data(),
            )
        case "rhs_urls":
            export_data_locally(
                table=rhs_urls.get_plant_urls(),
                dated=False,
            )
        case "rhs":
            rhs.get_plants_detail(pl.read_parquet("data/rhs_urls.parquet").to_dicts())
            pl.scan_pyarrow_dataset(ds.dataset("data/rhs/")).collect().write_parquet(
                "data/rhs.parquet"
            )

        case _:
            raise ValueError(f"Unhandled site: {params.site!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape nurseries, manage RHS data, or run the matching pipeline."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--site",
        help="Name of the site you would like to fetch data for.",
        choices=[*SCRAPED_NURSERIES, "rhs", "rhs_urls"],
    )
    mode.add_argument(
        "--matching",
        action="store_true",
        help="Run the matching pipeline against the latest scraped data.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="When used with --matching, skip the LLM fallback (deterministic only).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the freshness gate and re-scrape regardless of recent data.",
    )
    args = parser.parse_args()

    if args.matching:
        _run_matching(llm_enabled=not args.no_llm)
    else:
        main(args)
