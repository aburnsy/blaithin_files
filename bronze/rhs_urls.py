import requests
import json
from bs4 import BeautifulSoup
import re
from string import ascii_lowercase
import polars as pl

plant_type_mapping = {
    1: "Herbaceous Perennial",
    2: "Climber Wall Shrub",
    3: "Bedding",
    4: "Bulbs",
    5: "Ferns",
    6: "Shrubs",
    7: "Annual Biennial",
    8: "Alpine Rockery",
    9: "Roses",
    10: "Grasses",
    11: "Conservatory Greenhouse",
    12: "Fruit Edible",
    13: "Trees",
    14: "Houseplants",
    15: "Cactus Succulent",
    16: "Aquatic",
    17: "Bamboos",
    18: "Bogs",
    19: "Conifers",
    20: "Herbs",
    21: "Palms",
}


def get_plant_urls(plant_types: list = range(1, 22)):
    URL = "https://lwapp-uks-prod-psearch-01.azurewebsites.net/api/v1/plants/search/advanced"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    page_size = 1000

    plants = []

    for plant_type in plant_types:
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
                    )  # replace special characters with -
                    botanical_name_html = botanical_name_html.replace(
                        ".", ""
                    )  # replace certain characters with .
                    botanical_name_html = re.sub(r"[']", "", botanical_name_html)

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

            print(
                f"Found {len(temp_plants)} products for '{plant_type_mapping[plant_type]}' plant type and letter '{keywords}'"
            )
            plants.extend(temp_plants)

    plants = pl.DataFrame(plants)
    plants = plants.unique(maintain_order=True)
    return plants
