import json
import urllib.parse
from datetime import datetime
from string import ascii_lowercase

import polars as pl
import requests
from bs4 import BeautifulSoup

from src.scrapers.rhs_enums import PLANT_TYPE as plant_type_mapping


def _log(msg: str) -> None:
    """Print one line prefixed with HH:MM:SS, flushed immediately."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_plant_urls(plant_types: list | None = None):
    if plant_types is None:
        plant_types = list(range(1, 22))
    URL = "https://lwapp-uks-prod-psearch-01.azurewebsites.net/api/v1/plants/search/advanced"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    page_size = 1000

    plants = []

    total_types = len(plant_types)
    _log(f"RHS URL discovery starting — {total_types} plant types × 26 keyword letters")

    for type_idx, plant_type in enumerate(plant_types, start=1):
        type_label = plant_type_mapping.get(plant_type, str(plant_type))
        type_total_before = len(plants)
        _log(
            f"  [{type_idx}/{total_types}] plant_type={plant_type} "
            f"({type_label}) — querying a..z"
        )

        for keywords in list(ascii_lowercase):
            temp_plants = []
            offset = 0

            while (
                response := requests.post(
                    URL,
                    json.dumps(
                        {
                            "includeAggregation": False,
                            "pageSize": page_size,
                            "startFrom": offset,
                            "plantTypes": [str(plant_type)],
                            "keywords": keywords,
                        }
                    ),
                    headers=headers,
                )
            ).status_code == 200:
                results = json.loads(response.text)["hits"]
                if len(results) == 0:
                    # We have reached the end of this structure
                    break

                for result in results:
                    botanical_name = result["botanicalName"]
                    id = result["id"]

                    # Prep botanical name
                    botanical_name_base = BeautifulSoup(botanical_name, "html.parser")
                    botanical_name_base = (
                        botanical_name_base.text.strip()
                    )  # Get text between html characters
                    botanical_name_html = (
                        botanical_name_base.replace(" ", "-")
                        .replace("/", "-")
                        .replace("-&-", "-")
                        .replace("-+-", "-")
                        .replace("+-", "-")
                    )  # replace special characters with -
                    botanical_name_html = (
                        botanical_name_html.replace(".", "")
                        .replace("&", "")
                        .replace("'", "")
                    )  # replace certain characters with .
                    ## Just parsing the url does not work, so we need to do both
                    botanical_name_html = urllib.parse.quote(botanical_name_html)

                    plant_url = f"https://www.rhs.org.uk/plants/{id}/{botanical_name_html}/details"
                    temp_plants.append(
                        {
                            "id": id,
                            "botanical_name": botanical_name_base,
                            "plant_url": plant_url,
                            "source": "rhs_urls",
                        }
                    )
                offset += page_size

            plants.extend(temp_plants)

        type_added = len(plants) - type_total_before
        _log(
            f"  [{type_idx}/{total_types}] plant_type={plant_type} ({type_label}) "
            f"done — added {type_added} rows (running total {len(plants)})"
        )

    plants = pl.DataFrame(plants).unique(maintain_order=True).to_dicts()
    _log(f"Found {len(plants)} products")
    return plants
