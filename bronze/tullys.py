#!/usr/bin/env python
# coding: utf-8
from requests_html import HTMLSession
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import importlib


def parse_products(URL: str, category: str, products: list) -> list[dict]:
    results = []
    # Skip the first row as that as the heading though its not labeled as such
    for product in products[1:]:
        product_link = product.find("a", class_="productLink")
        product_url = urljoin(URL, product_link["href"])
        product_name = product.find("p", class_="productName").text
        product_code = product.find("p", class_="productCode").find("span").text
        image = product.find("div", class_="imageWrap").find("img")
        if image is None:
            img_url = None
        else:
            img_url = urljoin(URL, image["src"]).rsplit("&Thumbnail=true", 1)[0]
        description = product.find("p", class_="description").find("span").text
        price_exc_vat = (
            product.find("div", class_="priceVatExcCurrencySymbol")
            .find_all("span")[1]
            .text
        )
        price_inc_vat = round(float(price_exc_vat) * 1.135, 2)
        size = product.find("div", class_="columnField").find("span").text
        try:
            stock = int(product.find("div", class_="inStock").text)
        except ValueError:
            stock = 0
        results.append(
            {
                "source": "tullys",
                "source_url": URL,
                "product_url": product_url,
                "category": category,
                "product_name": product_name,
                "product_code": product_code,
                "img_url": img_url,
                "description": description,
                "price": price_inc_vat,
                "size": size,
                "stock": stock,
            }
        )
    return results


def parse_url(URL: str, category: str) -> list[dict]:
    print(f"Fetching data for {category} from {URL}")
    session = HTMLSession()
    page = session.get(URL)
    content = BeautifulSoup(page.content, "html.parser")
    products = content.table.find_all("tr")
    parsed_products = parse_products(URL=URL, category=category, products=products)
    print(f"Found {len(parsed_products)} products for {category}")
    return parsed_products


def get_product_data(config_file_name: str = "tullys") -> list[dict] | None:
    config = importlib.import_module("config." + config_file_name)
    results = []

    for URL, category in config.data_sources:
        results.extend(parse_url(URL=URL, category=category))
    return results
