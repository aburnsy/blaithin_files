#!/usr/bin/env python
# coding: utf-8
from requests_html import HTMLSession
from bs4 import BeautifulSoup
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
import importlib
import time


def selenium_setup() -> webdriver:
    driver = webdriver.Chrome()
    return driver


numeric_pattern_compiled = re.compile(r"(\d+)")


def extract_price_from_text(price_str):
    return float(re.sub(r"[^\d.\.]", "", price_str))


def fetch_data_interactive(
    product_url: str, source_url: str, category: str, driver: webdriver
) -> list:
    """There are multiple options for this product. Hence we need to make a selection and come back to this one"""
    results = []

    driver.get(product_url)

    try:
        select_element = driver.find_element(By.XPATH, '//select[@id="pa_pot-size"]')
    except NoSuchElementException:
        try:
            select_element = driver.find_element(
                By.XPATH, '//select[@id="pa_variation"]'
            )
        except NoSuchElementException:
            try:
                select_element = driver.find_element(
                    By.XPATH, '//select[@id="pa_size"]'
                )
            except NoSuchElementException:
                try:
                    select_element = driver.find_element(
                        By.XPATH, '//select[@id="pa_colour"]'
                    )
                except NoSuchElementException:
                    print(
                        f"Error fetching data for {product_url}. No dropdown options found."
                    )
                    return None

    select = Select(select_element)

    product_name = driver.find_element(
        By.XPATH, '//h1[@class="product_title entry-title"]'
    ).get_attribute("innerText")

    try:
        img_url = (
            driver.find_element(
                By.XPATH, '//div[@class="woocommerce-product-gallery__image"]'
            )
            .find_element(By.TAG_NAME, "img")
            .get_attribute("src")
        )
    except NoSuchElementException:
        img_url = None

    try:
        description = (
            driver.find_element(By.XPATH, '//div[@id="tab-description"]')
            .find_element(By.TAG_NAME, "p")
            .get_attribute("innerText")
        )
    except NoSuchElementException:
        try:
            description = driver.find_element(
                By.XPATH,
                '//section[@class="template-article__editor-content editor-content"]',
            ).get_attribute("innerText")
        except NoSuchElementException:
            description = None

    for option_value, option_name in [
        (option.get_attribute("value"), option.get_attribute("innerText"))
        for option in select_element.find_elements(By.TAG_NAME, "option")
    ]:
        if option_value == "Choose an option" or option_value == "":
            continue
        else:
            select.select_by_value(option_value)

            # Sleeping here instead of waiting. The data is stored in browser in a form, so no round trips are required.
            # Because of how prices are displayed, its hard to verify that the prices etc are ready for consumption
            time.sleep(0.3)

            try:
                price = (
                    driver.find_element(
                        By.XPATH,
                        '//div[@class="woocommerce-variation single_variation"]',
                    )
                    .find_element(By.TAG_NAME, "bdi")
                    .get_attribute("innerText")
                )
            except NoSuchElementException:
                prices = driver.find_elements(
                    By.XPATH, '//span[@class="woocommerce-Price-amount amount"]'
                )
                for price in prices:
                    p = price.find_element(By.TAG_NAME, "bdi")
                    if p.is_displayed():
                        price = p.get_attribute("innerText")
                        break
            price_inc_vat = extract_price_from_text(price)

            try:
                stock_str = driver.find_element(
                    By.XPATH, '//p[@class="stock in-stock"]'
                ).get_attribute("innerText")
                stock_search = re.search(numeric_pattern_compiled, stock_str)
                if stock_search:
                    stock = stock_search.group(0)
                else:
                    stock = 0
            except NoSuchElementException:
                stock = 0

            # Leave as raw information - we will process this in silver layer
            size = option_name

            results.append(
                {
                    "source": "carragh",
                    "source_url": source_url,
                    "product_url": product_url,
                    "category": category,
                    "product_name": product_name,
                    "img_url": img_url,
                    "description": description,
                    "price": price_inc_vat,
                    "size": size,
                    "stock": stock,
                }
            )
    return results


def parse_url(URL: str, category: str, driver: webdriver) -> list[dict]:
    print(f"Fetching data for {category} from {URL}")
    session = HTMLSession()
    page_number = 1
    results = []

    while (page := session.get(f"{URL}/page/{page_number}")).status_code == 200:
        content = BeautifulSoup(page.content, "html.parser")
        products = content.find(
            "ul", class_="products elementor-grid columns-3"
        ).find_all("li")

        for product in products:
            product_url = product.a["href"]
            if result := fetch_data_interactive(
                product_url=product_url,
                source_url=URL,
                category=category,
                driver=driver,
            ):
                results.extend(result)
        page_number += 1

    print(f"Found {len(results)} products for {category}")

    return results


def get_product_data(config_file_name: str = "carragh") -> list[dict] | None:
    config = importlib.import_module("config." + config_file_name)
    results = []
    driver = selenium_setup()
    for URL, category in config.data_sources:
        results.extend(parse_url(URL=URL, category=category, driver=driver))
    driver.quit()
    return results
