#! .venv/Scripts/python.exe

import argparse
from src.common.storage import export_data_locally
from src.scrapers import tullys, quickcrop, gardens4you, carragh, arboretum, rhs_urls, rhs, hedgingie
import polars as pl
import pyarrow.dataset as ds
from datetime import date
from pathlib import Path

NURSERIES = ("tullys", "quickcrop", "gardens4you", "carragh", "arboretum")


def _run_matching(*, llm_enabled: bool) -> None:
    """Load latest per-nursery parquets + RHS, run the matching pipeline, write output."""

    from src.matching.run import run_with_llm_fallback

    frames = []
    for nursery in NURSERIES:
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
            export_data_locally(
                table=carragh.get_product_data(),
            )
            export_data_locally(table=tullys.get_product_data())
            export_data_locally(table=quickcrop.get_product_data())
            export_data_locally(table=gardens4you.get_product_data())
            export_data_locally(
                table=arboretum.get_product_data(),
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape nurseries, manage RHS data, or run the matching pipeline."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--site",
        help="Name of the site you would like to fetch data for.",
        choices=[
            "tullys",
            "quickcrop",
            "gardens4you",
            "carragh",
            "arboretum",
            "hedgingie",
            "rhs",
            "rhs_urls",
        ],
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
    args = parser.parse_args()

    if args.matching:
        _run_matching(llm_enabled=not args.no_llm)
    else:
        main(args)
