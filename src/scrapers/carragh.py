#!/usr/bin/env python
import importlib
import re

from bs4 import BeautifulSoup
from requests_html import HTMLSession
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait


def selenium_setup() -> webdriver:
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    return webdriver.Chrome(options=opts)


numeric_pattern_compiled = re.compile(r"(\d+)")

_VARIATION_PRICE_JS = (
    "var b = document.querySelector("
    "'div.woocommerce-variation.single_variation bdi'); "
    "return b ? b.innerText.trim() : '';"
)
_FALLBACK_PRICE_JS = (
    "var nodes = document.querySelectorAll('span.woocommerce-Price-amount bdi'); "
    "for (var n of nodes) {"
    "  if (n.offsetParent !== null && n.innerText.trim()) "
    "    return n.innerText.trim();"
    "} return '';"
)


def extract_price_from_text(price_str):
    return float(re.sub(r"[^\d.\.]", "", price_str))


def fetch_data_interactive(
    product_url: str, source_url: str, category: str, driver: webdriver
) -> list:
    """There are multiple options for this product. Hence we need to make a selection and come back to this one"""
    results = []

    driver.get(product_url)

    select_xpath = None
    for candidate in (
        '//select[@id="pa_pot-size"]',
        '//select[@id="pa_variation"]',
        '//select[@id="pa_size"]',
        '//select[@id="pa_colour"]',
    ):
        try:
            select_element = driver.find_element(By.XPATH, candidate)
            select_xpath = candidate
            break
        except NoSuchElementException:
            continue
    if select_xpath is None:
        print(f"Error fetching data for {product_url}. No dropdown options found.")
        return None

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

    # Snapshot all option values up front — the select itself may be re-rendered
    # by WooCommerce after each selection, so the element list can go stale.
    option_pairs: list[tuple[str, str]] = []
    for option in select_element.find_elements(By.TAG_NAME, "option"):
        value = option.get_attribute("value")
        name = option.get_attribute("innerText")
        if value and value != "Choose an option":
            option_pairs.append((value, name))

    for option_value, option_name in option_pairs:
        try:
            fresh_select_element = driver.find_element(By.XPATH, select_xpath)
            Select(fresh_select_element).select_by_value(option_value)
        except (StaleElementReferenceException, NoSuchElementException):
            print(
                f"Skip option {option_value!r} (stale/missing). URL: {product_url}"
            )
            continue

        # The woocommerce-variation div is empty in the static HTML; WooCommerce
        # JS populates it (with a <bdi> price element) asynchronously after the
        # option is selected. Read the price via execute_script so we don't
        # hold a WebElement reference that can go stale across the re-render.
        try:
            price = WebDriverWait(driver, 10).until(
                lambda d: d.execute_script(_VARIATION_PRICE_JS) or False
            )
        except TimeoutException:
            # Fallback: variations sometimes render their price outside the
            # single_variation block — take the first visible bdi inside any
            # woocommerce-Price-amount span.
            price = driver.execute_script(_FALLBACK_PRICE_JS)
            if not price:
                print(
                    f"No price for {option_value} on {product_url}. Skipping."
                )
                continue
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
