from requests_html import HTMLSession
from bs4 import BeautifulSoup
import polars as pl
import pyarrow.parquet as pq
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
import traceback
from selenium.webdriver.support.wait import WebDriverWait
import time

try:
    from .common import ScrollToBottom
except ImportError:
    from common import ScrollToBottom
import os


def extract_detailed_plant_data(plant: dict, plant_content) -> dict:
    id_ = plant["id"]
    botanical_name = plant["botanical_name"]
    plant_url = plant["plant_url"]
    try:
        common_name = plant_content.find("p", class_="summary summary--sub").text
        if common_name == "":
            common_name = None
    except AttributeError:
        common_name = None

    try:
        plant_type = [
            pt.text.strip()
            for pt in plant_content.find_all("span", class_="label ng-star-inserted")
        ]
    except AttributeError:
        print(f"Cannot find plant type for plant {plant_url}")
        plant_type = []

    try:
        description = plant_content.find("p", class_="ng-star-inserted").text.strip()
    except AttributeError:
        print(f"Cannot find description for plant {plant_url}")
        description = None

    try:
        plant_content.find("img", attrs={"alt": "RHS AGM"}).text
        is_rhs_award_winner = True
    except AttributeError:
        is_rhs_award_winner = False

    try:
        plant_content.find("img", attrs={"alt": "RHS Plants for pollinators"}).text
        is_pollinator_plant = True
    except AttributeError:
        is_pollinator_plant = False

    # Size, Growing Conditions, Colour&Scent, Position
    for plant_attributes_panel in plant_content.find_all(
        "div", class_="plant-attributes__panel"
    ):
        panel_heading = plant_attributes_panel.find(
            class_="plant-attributes__heading"
        ).text.lower()
        if panel_heading == "size":
            for attribute in plant_attributes_panel.find_all(class_="flag__body"):
                if attribute.find(lambda tag: "Ultimate height" in tag.text):
                    height = (
                        attribute.contents[-1]
                        .strip()
                        .replace("–", "-")
                        .replace("â", "-")
                        .replace("-\x80\x93", "-")
                    )
                elif attribute.find(lambda tag: "Ultimate spread" in tag.text):
                    spread = (
                        attribute.contents[-1]
                        .strip()
                        .replace("–", "-")
                        .replace("â", "-")
                        .replace("-\x80\x93", "-")
                    )
                elif attribute.find(lambda tag: "Time to ultimate height" in tag.text):
                    time_to_ultimate_spread = (
                        attribute.contents[-1]
                        .strip()
                        .replace("–", "-")
                        .replace("â", "-")
                        .replace("-\x80\x93", "-")
                    )
        elif panel_heading == "growing conditions":
            soils = [
                soil_element.text
                for soil_element in plant_attributes_panel.find_all(
                    "div", class_="flag__body"
                )
            ]
            for attribute in plant_attributes_panel.find_all(class_="l-module"):
                if attribute.find(lambda tag: "Moisture" in tag.text):
                    moisture = (
                        attribute.find("span")
                        .text.strip()
                        .replace("–", "-")
                        .replace("â", "-")
                        .replace("-\x80\x93", "-")
                    )
                elif attribute.find(lambda tag: "pH" in tag.text):
                    ph = [
                        attr.text.replace(",", "").strip()
                        for attr in attribute.find_all("span")
                    ]
        elif "colour" in panel_heading:
            if len(table := plant_attributes_panel.find("table")) > 0:
                data = []
                for row in table.find_all("tr")[1:]:
                    row_data = []
                    for header in row.find_all("th"):
                        row_data.append(header.text)
                    for cell in row.find_all("td"):
                        row_data.append(cell.text.strip().split())
                    data.append(row_data)
                colour_and_scent = data  # noqa: F841
                # df = pl.DataFrame(
                #     data, schema=["Season", "Stem", "Flower", "Foliage", "Fruit"]
                # )
                # print(df)
        elif panel_heading == "position":
            try:
                sun_exposure = [
                    se.text
                    for se in plant_attributes_panel.find(
                        "ul", class_="list-inline ng-star-inserted"
                    ).find_all("li")
                ]
            # Example with no exposure: https://www.rhs.org.uk/plants/239046/delphinium-lance-bearer/details
            except AttributeError:
                sun_exposure = None

            aspect = [
                asp.text.replace("\x80\x93", "-").replace("â", "").replace(" or ", "")
                for asp in plant_attributes_panel.find("p").find_all("span")
            ]

            expos_hard = plant_attributes_panel.find(
                "div", class_="l-row l-row--space l-row--auto-clear"
            ).find_all("div", class_="l-module")
            exposure = [
                exp.text.replace(" or ", "") for exp in expos_hard[0].find_all("span")
            ]
            try:  # Example with no hardiness https://www.rhs.org.uk/plants/372810/phalaenopsis-picasso/details
                hardiness = expos_hard[1].find_all("span")[-1].text
            except IndexError:
                hardiness = None

    bottom_panel = plant_content.find("div", class_="panel__body").find_all(string=True)
    bottom_panel = [entry for entry in bottom_panel if entry.strip() != ""]
    i = 0
    while i < len(bottom_panel):
        value = bottom_panel[i]
        if str(value).strip().endswith(" or") or str(value).strip().endswith(","):
            bottom_panel[i] = bottom_panel[i] + bottom_panel[i + 1]
            del bottom_panel[i + 1]
            i -= 1
        i += 1

    bottom_panel_dict = {}
    for key, value in zip(bottom_panel[0::2], bottom_panel[1::2]):
        bottom_panel_dict[key] = value
    try:  # Example https://www.rhs.org.uk/plants/78738/blackstonia-perfoliata/details
        foliage = [
            entry.strip() for entry in bottom_panel_dict["Foliage"].split(" or ")
        ]
    except KeyError:
        foliage = None
    habit = [entry.strip() for entry in bottom_panel_dict["Habit"].split(",")]

    extract = {
        "id": id_,
        "source": "rhs",
        "plant_url": plant_url,
        "botanical_name": botanical_name,
        "common_name": common_name,
        "plant_type": plant_type,
        "description": description,
        "is_rhs_award_winner": is_rhs_award_winner,
        "is_pollinator_plant": is_pollinator_plant,
        "height": height,
        "spread": spread if "spread" in locals() else None,
        "time_to_ultimate_spread": time_to_ultimate_spread,
        "soils": soils,
        "moisture": moisture if "moisture" in locals() else None,
        "ph": ph if "ph" in locals() else None,
        # "colour_and_scent": colour_and_scent,
        "sun_exposure": sun_exposure,
        "aspect": aspect,
        "exposure": exposure,
        "hardiness": hardiness,
        "foliage": foliage,
        "habit": habit,
    }
    return extract


def fetch_sample_plants() -> list[dict]:
    """Fetch a sample of locally stored plants for scraping on rhs website"""
    print("Fetching sample data from rhs_urls parquet file")
    return pl.read_parquet("data\\rhs_urls.parquet").sample(1000).to_dicts()


def get_plants_detail(plants: list[dict]) -> None:
    session = HTMLSession()
    driver = selenium_setup()
    if not os.path.exists("data\\rhs"):
        os.mkdir("data\\rhs")
    for plant in plants:
        plant_url = plant["plant_url"]
        file_name = f"data\\rhs\\{plant["id"]}.parquet"
        if os.path.isfile(file_name):
            continue
            # pass
        if (plant_page := session.get(plant_url)).status_code != 200:
            print(f"Given plant URL '{plant_url}' is incorrect.")
            continue
        try:
            extract = extract_detailed_plant_data(
                plant=plant,
                plant_content=BeautifulSoup(plant_page.content, "html.parser"),
            )
        except Exception:
            try:
                print(f"Trying Selenium {plant["plant_url"]}")
                driver.get(plant_url)
                WebDriverWait(driver, 100).until(ScrollToBottom(driver, 2))
                extract = extract_detailed_plant_data(
                    plant=plant,
                    plant_content=BeautifulSoup(driver.page_source, "html.parser"),
                )

            except Exception:
                traceback.print_exc()
                print(f"ERROR Could not fetch data for {plant["plant_url"]}")
                continue

        df = pl.DataFrame([extract])

        df.write_parquet(file_name)

    driver.quit()


def selenium_setup() -> webdriver:
    driver = webdriver.Chrome()
    return driver


# get_plants_detail(
#     [
#         {
#             "plant_url": "https://www.rhs.org.uk/plants/83693/tillandsia-albertiana/details",
#             "id": 83693,
#             "botanical_name": "Tillandsia albertiana",
#         },
#     ]
# )
