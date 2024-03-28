import argparse
import cloud_storage
from bronze import tullys, quickcrop, gardens4you, carragh, arboretum


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

        case _:
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
        ],
    )
    args = parser.parse_args()
    main(args)
