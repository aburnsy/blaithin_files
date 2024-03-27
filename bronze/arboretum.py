#!/usr/bin/env python
# coding: utf-8
from bs4 import BeautifulSoup
from requests_html import HTMLSession
from selenium import webdriver
from selenium.webdriver.common.by import By
import re
from selenium.webdriver.support.wait import WebDriverWait
import importlib

try:
    from .common import ScrollToBottom
except ImportError:
    from common import ScrollToBottom

size_pattern_cm = re.compile(r"\d+\s*cm", flags=re.IGNORECASE)
size_pattern_litre = re.compile(r"\d+\s*ltr", flags=re.IGNORECASE)
size_pattern_litre2 = re.compile(r"\d+\s*litre", flags=re.IGNORECASE)


def extract_price_from_text(price_str):
    return float(re.sub(r"[^\d.\.]", "", price_str))


multibuy_pattern_deal = re.compile(r"(\d+ x \w+)")
multibuy_pattern_trees = re.compile(r"(\d+ Tree)", flags=re.IGNORECASE)
multibuy_pattern_pack = re.compile(r"(\d+\s*-*Pack)", flags=re.IGNORECASE)
multibuy_pattern_plant = re.compile(r"(\d+ Plant)", flags=re.IGNORECASE)
numeric_pattern_compiled = re.compile(r"(\d+)")


def extract_quantity_from_text(product_text: str) -> int:
    multibuy_str = (
        re.search(multibuy_pattern_deal, product_text)
        or re.search(multibuy_pattern_trees, product_text)
        or re.search(multibuy_pattern_pack, product_text)
        or re.search(multibuy_pattern_plant, product_text)
    )
    if multibuy_str:
        return int(re.search(numeric_pattern_compiled, multibuy_str.group(0)).group(0))
    return 1


def extract_size_from_product(product_content, product_name, product_url) -> str:
    try:
        product_characteristics = product_content.find(
            "div", attrs={"itemprop": "description"}
        ).find_all("li")
        for characteristic in product_characteristics:
            if "size" in characteristic.text.lower():
                return characteristic.text.lower().replace("pot size:", "").strip()
    except AttributeError:
        print(f"Could not find size characteristics for {product_url}")

    if size_cm := re.search(size_pattern_cm, product_name):
        return size_cm.group(0).replace(" ", "")
    if size_l := re.search(size_pattern_litre, product_name):
        return size_l.group(0)
    if size_l := re.search(size_pattern_litre2, product_name):
        return size_l.group(0)

    print(f"no size for {product_url}")
    return "9 cm"  # Size isn't specified so we default to 9cm


def fetch_data(
    product_url: str, source_url: str, category: str, session: HTMLSession
) -> dict:
    product_page = session.get(product_url)
    product_html = BeautifulSoup(product_page.content, "lxml")
    product_content = product_html.find("div", class_="col-md-12 product-content")

    product_name = product_content.find("h1", attrs={"itemprop": "name"}).text

    img_url = product_content.find("a", class_="product-lightbox-btn")["href"]

    try:
        price_inc_vat_str = product_content.find(
            "span", attrs={"itemprop": "price"}
        ).text
    except AttributeError:
        price_inc_vat_str = product_content.find(
            "span", attrs={"itemprop": "priceCurrency"}
        ).text
    price_inc_vat = extract_price_from_text(price_inc_vat_str)

    size = extract_size_from_product(product_content, product_name, product_url)

    quantity = extract_quantity_from_text(product_name)

    try:
        stock_options = product_content.find(
            "select", attrs={"name": "quantity"}
        ).find_all("option")
        stock = max([int(option.text) for option in stock_options])
    except AttributeError:
        stock = 0

    description = product_content.find(
        "div", attrs={"itemprop": "description"}
    ).p.text.strip()

    return {
        "source": "arboretum",
        "source_url": source_url,
        "product_url": product_url,
        "category": category,
        "product_name": product_name,
        "img_url": img_url,
        "description": description,
        "price": price_inc_vat,
        "size": size,
        "stock": stock,
        "quantity": quantity,
    }


def selenium_setup() -> webdriver:
    driver = webdriver.Chrome()
    return driver


def parse_url(URL: str, category: str, driver: webdriver) -> list[dict]:
    print(f"Fetching data for {category} from {URL}")
    session = HTMLSession()

    driver.get(URL)
    WebDriverWait(driver, 100).until(ScrollToBottom(driver, 2))
    results = []

    products = driver.find_element(
        By.XPATH, '//div[@class="shop-filters-area"]'
    ).find_elements(By.XPATH, '//div[@class="content-product"]')
    for product in products:
        product_url = product.find_element(By.TAG_NAME, "a").get_attribute("href")

        if result := fetch_data(
            product_url=product_url, source_url=URL, category=category, session=session
        ):
            results.append(result)

    print(f"Found {len(results)} products for {category}")

    return results


def get_product_data(config_file_name: str = "arboretum") -> list[dict] | None:
    config = importlib.import_module("config." + config_file_name)
    results = []
    driver = selenium_setup()
    for URL, category in config.data_sources:
        results.extend(parse_url(URL=URL, category=category, driver=driver))
    driver.quit()
    return results
