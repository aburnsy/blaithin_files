#! .venv/Scripts/python.exe

import argparse
import os

import polars as pl

from src.common.freshness import should_scrape
from src.common.nurseries import scraped_nursery_slugs
from src.common.storage import export_data_locally
from src.scrapers import (
    arboretum,
    ardcarne,
    ballyrobert,
    beattys,
    bloombox,
    brown_envelope,
    bulbi,
    carragh,
    connecting_to_nature,
    cullen,
    david_austin,
    doonwood,
    dutch_bulbs,
    dutchgrown,
    esker_daffodils,
    famous_roses,
    farmer_gracy,
    fluwel,
    fruit_hill_farm,
    future_forests,
    gardens4you,
    greengardenflowerbulbs,
    hedges_direct,
    hedgingie,
    hopeless_botanics,
    howbert_mays,
    ireland_trees,
    johnstown,
    jparkers,
    mid_ulster,
    mount_venus,
    mr_middleton,
    newlands,
    organic_centre,
    peter_nyssen,
    promesse,
    plant_store,
    plantgift,
    quickcrop,
    rhs,
    rhs_urls,
    seed_savers,
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
        case "hopeless_botanics":
            export_data_locally(
                table=hopeless_botanics.get_product_data(),
            )
        case "bloombox":
            export_data_locally(
                table=bloombox.get_product_data(),
            )
        case "mid_ulster":
            export_data_locally(
                table=mid_ulster.get_product_data(),
            )
        case "farmer_gracy":
            export_data_locally(
                table=farmer_gracy.get_product_data(),
            )
        case "mount_venus":
            export_data_locally(
                table=mount_venus.get_product_data(),
            )
        case "cullen":
            export_data_locally(
                table=cullen.get_product_data(),
            )
        case "hedges_direct":
            export_data_locally(
                table=hedges_direct.get_product_data(),
            )
        case "famous_roses":
            export_data_locally(
                table=famous_roses.get_product_data(),
            )
        case "bulbi":
            export_data_locally(
                table=bulbi.get_product_data(),
            )
        case "greengardenflowerbulbs":
            export_data_locally(
                table=greengardenflowerbulbs.get_product_data(),
            )
        case "johnstown":
            export_data_locally(
                table=johnstown.get_product_data(),
            )
        case "mr_middleton":
            export_data_locally(
                table=mr_middleton.get_product_data(),
            )
        case "jparkers":
            export_data_locally(
                table=jparkers.get_product_data(),
            )
        case "ardcarne":
            export_data_locally(
                table=ardcarne.get_product_data(),
            )
        case "promesse":
            export_data_locally(
                table=promesse.get_product_data(),
            )
        case "peter_nyssen":
            export_data_locally(
                table=peter_nyssen.get_product_data(),
            )
        case "ireland_trees":
            export_data_locally(
                table=ireland_trees.get_product_data(),
            )
        case "doonwood":
            export_data_locally(
                table=doonwood.get_product_data(),
            )
        case "fruit_hill_farm":
            export_data_locally(
                table=fruit_hill_farm.get_product_data(),
            )
        case "dutch_bulbs":
            export_data_locally(
                table=dutch_bulbs.get_product_data(),
            )
        case "organic_centre":
            export_data_locally(
                table=organic_centre.get_product_data(),
            )
        case "seed_savers":
            export_data_locally(
                table=seed_savers.get_product_data(),
            )
        case "esker_daffodils":
            export_data_locally(
                table=esker_daffodils.get_product_data(),
            )
        case "rhs_urls":
            export_data_locally(
                table=rhs_urls.get_plant_urls(),
                dated=False,
            )
        case "rhs":
            rhs.get_plants_detail(pl.read_parquet("data/rhs_urls.parquet").to_dicts())

        case _:
            raise ValueError(f"Unhandled site: {params.site!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape a nursery or refresh the RHS dictionary."
    )
    parser.add_argument(
        "--site",
        required=True,
        help="Name of the site you would like to fetch data for.",
        choices=[*SCRAPED_NURSERIES, "rhs", "rhs_urls"],
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the freshness gate and re-scrape regardless of recent data.",
    )
    args = parser.parse_args()

    # Freshness gate runs BEFORE configuring per-site file logging so a skip
    # doesn't overwrite the previous successful scrape log at logs/<site>.log.
    if args.site in SCRAPED_NURSERIES:
        force = _force_from_env_or_arg(args.force)
        max_age = _max_age_days_from_env()
        run, reason = should_scrape(args.site, max_age_days=max_age, force=force)
        if not run:
            print(reason)
            raise SystemExit(0)
        print(reason)

    from src.common.logging import configure as _configure_logging
    _configure_logging(source=args.site, force=True)
    main(args)
