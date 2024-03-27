#!/usr/bin/env python
# coding: utf-8
from requests_html import HTMLSession
from bs4 import BeautifulSoup
import re
import importlib

session = HTMLSession()

quantity_pattern = re.compile(r"^\d+x$")
stock_pattern = re.compile(r"\d+")
size_pattern_cm = re.compile(r"\d+\s*cm", flags=re.IGNORECASE)
size_pattern_litre = re.compile(r"\d+\s*ltr", flags=re.IGNORECASE)
size_pattern_pval = re.compile(r"P\s*\d+")


def extract_size_from_url(product_url: str) -> str:
    page = session.get(product_url)
    content = BeautifulSoup(page.content, "html.parser")
    if height := content.find("td", {"data-th": "aa_height", "class": "col data"}):
        return re.search(size_pattern_cm, height.text).group(0)
    if del_as := content.find("td", {"data-th": "Delivered as", "class": "col data"}):
        if "roots" in del_as.text.lower():
            return "Bare Root"
        elif "pot" in del_as.text.lower():
            return "9 cm"
        elif "seeds" in del_as.text.lower():
            return "Seeds"
        else:
            raise Exception(f"NOT FOUND for {product_url} with {del_as.text}")

    if attr_desc := content.find("div", class_="product attribute description"):
        if elements := attr_desc.select("div"):
            for element in elements:
                if size_fnd := re.search(size_pattern_cm, element.text):
                    return size_fnd.group(0)
        if elements := attr_desc.select("li"):
            for element in elements:
                if size_fnd := re.search(size_pattern_cm, element.text):
                    return size_fnd.group(0)
    if attr_main := content.find("div", class_="att-container"):
        if elements := attr_main.select("div"):
            for element in elements:
                if "seed" in element.text.lower():
                    return "Seeds"
    return "Bare Root"


def extract_price_from_text(price_str):
    return float(re.sub(r"[^\d.\.]", "", price_str))


def parse_products(URL: str, category: str, products: list) -> list[dict]:
    results = []

    # Skip the first row as that as the heading though its not labeled as such
    for product in products:
        product_url = product.find("a")["href"]
        try:
            product_name = product.find("div", class_="botanical-name").text
        except AttributeError:
            product_name = product.find(
                "strong", class_="product name product-item-name"
            ).a.text

        image = product.find("img", class_="product-image-photo")
        try:
            img_url = image["data-amsrc"]  # Weird issue with collection imgs
        except KeyError:
            img_url = image["src"]

        description = product.find(
            "div", class_="product description product-item-description"
        ).text
        price_inc_vat = extract_price_from_text(
            product.find("span", class_="price").text
        )

        misc = [
            entry.text.lower().strip()
            for entry in product.find_all("div", class_="amlabel-text")
        ]

        # size
        if "roots" in misc or "tubers" in misc:
            size = "Bare Root"
        elif "seeds" in misc:
            size = "Seeds"
        else:
            # ø 9cm
            filtered_list = [
                re.search(size_pattern_cm, entry).group(0)
                for entry in misc
                if re.search(size_pattern_cm, entry)
            ]
            if len(filtered_list) == 1:
                size = filtered_list[0]
            else:
                # 3 ltr
                filtered_list = [
                    re.search(size_pattern_litre, entry).group(0)
                    for entry in misc
                    if re.search(size_pattern_litre, entry)
                ]
                if len(filtered_list) == 1:
                    size = filtered_list[0].replace("tr", "")
                else:
                    temp_str = product.find(
                        "strong", class_="product name product-item-name"
                    ).a.text
                    if size_cm := re.search(size_pattern_cm, temp_str):
                        size = size_cm.group(0).replace(" ", "")
                    elif size_p := re.search(size_pattern_pval, temp_str):
                        size = size_p.group(0)
                    elif size_l := re.search(size_pattern_litre, temp_str):
                        size = size_l.group(0).replace("tr", "")
                    elif "bare root" in temp_str.lower():
                        size = "Bare Root"
                    else:
                        size = extract_size_from_url(product_url=product_url)

        # quantity
        filtered_list = [
            int(entry.replace("x", ""))
            for entry in misc
            if quantity_pattern.match(entry)
        ]
        if len(filtered_list) == 1:
            quantity = filtered_list[0]
        else:
            quantity = 1

        stock_str = re.search(
            stock_pattern, product.find("span", class_="amstockstatus").text
        )
        if stock_str:
            stock = int(stock_str.group(0))
        else:
            stock = 0

        results.append(
            {
                "source": "gardens4you",
                "source_url": URL,
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
        )
    return results


def parse_url(URL: str, category: str) -> list[dict]:
    page_number = 1
    results = []

    while (page := session.get(f"{URL}?p={page_number}")).status_code == 200:
        content = BeautifulSoup(page.content, "html.parser")
        if content.find("div", class_="message info empty"):
            break
        products = content.find(class_="products list items product-items").find_all(
            "li"
        )
        results.extend(parse_products(URL=URL, category=category, products=products))

        page_number += 1

    print(f"Found {len(results)} products for {category}")
    return results


def get_product_data(config_file_name: str = "gardens4you") -> list[dict] | None:
    config = importlib.import_module("config." + config_file_name)
    results = []

    for URL, category in config.data_sources:
        results.extend(parse_url(URL=URL, category=category))
    return results
