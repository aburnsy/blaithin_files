#! .venv/Scripts/python.exe

import argparse
from src.common.storage import export_data_locally
from src.scrapers import tullys, quickcrop, gardens4you, carragh, arboretum, rhs_urls, rhs
import polars as pl
import pyarrow.dataset as ds


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
        description="Scrape data from sites and store to gcs bronze area"
    )
    parser.add_argument(
        "--site",
        help="Name of the site you would like to fetch data for.",
        choices=[
            "tullys",
            "quickcrop",
            "gardens4you",
            "carragh",
            "arboretum",
            "rhs",
            "rhs_urls",
        ],
    )
    args = parser.parse_args()
    main(args)
