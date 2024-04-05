import argparse
import cloud_storage
from bronze import tullys, quickcrop, gardens4you, carragh, arboretum, rhs_urls, rhs
import polars as pl


def main(params):
    match params.site:
        case "tullys":
            cloud_storage.export_data_locally(
                table=tullys.get_product_data(),
            )
        case "quickcrop":
            cloud_storage.export_data_locally(
                table=quickcrop.get_product_data(),
            )
        case "gardens4you":
            cloud_storage.export_data_locally(
                table=gardens4you.get_product_data(),
            )
        case "carragh":
            cloud_storage.export_data_locally(
                table=carragh.get_product_data(),
            )
        case "arboretum":
            cloud_storage.export_data_locally(
                table=arboretum.get_product_data(),
            )
        case "rhs_urls":
            cloud_storage.export_data_locally(
                table=rhs_urls.get_plant_urls(),
                dated=False,
            )
        case "rhs":
            rhs.get_plants_detail(pl.read_parquet("data\\rhs_urls.parquet").to_dicts())

        case _:
            cloud_storage.export_data_locally(
                table=rhs_urls.get_plant_urls(),
                dated=False,
            )

            rhs.get_plants_detail(pl.read_parquet("data\\rhs_urls.parquet").to_dicts())
            cloud_storage.export_data_locally(
                table=carragh.get_product_data(),
            )
            cloud_storage.export_data_locally(table=tullys.get_product_data())
            cloud_storage.export_data_locally(table=quickcrop.get_product_data())
            cloud_storage.export_data_locally(table=gardens4you.get_product_data())
            cloud_storage.export_data_locally(
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
