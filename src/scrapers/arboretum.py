"""Arboretum scraper — Wexford garden centre, custom platform.

The shop is at ``/shop/products/<top>/<sub>/<leaf>/page-N.html``. Category
pages render products inside ``div.shop-filters-area > div.content-product``;
individual product pages carry the rich data we keep (price, size, stock,
description). Both kinds of page need JS rendering, so we drive Selenium.

Coverage strategy: bootstrap the category list by visiting one known leaf
and harvesting every ``/shop/products/.../page-1.html`` URL from the left
nav (the site exposes its full category tree in the navigation panel on
every leaf page). This replaces the legacy hand-picked 16-seed list.
See [[full-coverage]] memory.
"""

#!/usr/bin/env python
import re

from bs4 import BeautifulSoup
from requests_html import HTMLSession
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

try:
    from .common import ScrollToBottom
except ImportError:
    from common import ScrollToBottom

_BASE = "https://www.arboretum.ie"
# Bootstrap URL — any leaf with the full left-nav rendered will do.
_BOOTSTRAP_URL = (
    "https://www.arboretum.ie/shop/products/plants-seeds-and-bulbs/perennials/page-1.html"
)
_CATEGORY_HREF_RE = re.compile(r"/shop/products/[a-z0-9][a-z0-9_\-/]*/page-1\.html")

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
) -> dict | None:
    try:
        product_page = session.get(product_url)
        product_html = BeautifulSoup(product_page.content, "lxml")
        product_content = product_html.find("div", class_="col-md-12 product-content")
        if product_content is None:
            return None

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

        try:
            description = product_content.find(
                "div", attrs={"itemprop": "description"}
            ).p.text.strip()
        except AttributeError:
            description = None

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
    except Exception as e:  # noqa: BLE001
        print(f"  parse failed for {product_url}: {e}")
        return None


def selenium_setup() -> webdriver.Chrome:
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    return webdriver.Chrome(options=opts)


def discover_category_urls(driver: webdriver.Chrome) -> list[str]:
    """Bootstrap the full category list from the shop's left-nav.

    Visits one known leaf page (which renders the full category tree)
    and extracts every ``/shop/products/.../page-1.html`` URL. Returns
    absolute URLs, deduplicated.
    """
    print(f"Discovering categories via {_BOOTSTRAP_URL}")
    driver.get(_BOOTSTRAP_URL)
    WebDriverWait(driver, 30).until(
        lambda d: "shop-filters-area" in d.page_source
        or "404" in (d.title or "")
    )
    html = driver.page_source
    paths = set(_CATEGORY_HREF_RE.findall(html))
    urls = sorted({_BASE + p for p in paths})
    print(f"Discovered {len(urls)} category leaf URLs")
    return urls


def category_label(url: str) -> str:
    """Best-effort label from a category URL.

    /shop/products/plants-seeds-and-bulbs/perennials/page-1.html -> "Perennials"
    /shop/products/gardening/lawncare/lawn-seed/page-1.html -> "Lawn Seed"
    """
    path = url.replace(_BASE, "").rstrip("/")
    # Strip "/page-N.html" and take last segment
    parts = path.rsplit("/", 2)
    if len(parts) >= 2:
        leaf = parts[-2]
        return leaf.replace("-", " ").title()
    return ""


def parse_url(URL: str, category: str, driver: webdriver.Chrome) -> list[dict]:
    print(f"Fetching data for {category} from {URL}")
    session = HTMLSession()
    results: list[dict] = []
    try:
        driver.get(URL)
        WebDriverWait(driver, 30).until(ScrollToBottom(driver, 2))
    except Exception as e:  # noqa: BLE001
        print(f"  load failed: {e}")
        return results

    try:
        filters_area = driver.find_element(By.XPATH, '//div[@class="shop-filters-area"]')
    except Exception:  # noqa: BLE001
        print(f"  no shop-filters-area on {URL}")
        return results

    products = filters_area.find_elements(By.XPATH, '//div[@class="content-product"]')
    for product in products:
        try:
            product_url = product.find_element(By.TAG_NAME, "a").get_attribute("href")
        except Exception:  # noqa: BLE001
            continue
        if result := fetch_data(
            product_url=product_url, source_url=URL, category=category, session=session
        ):
            results.append(result)

    print(f"Found {len(results)} products for {category}")
    return results


def get_product_data() -> list[dict]:
    driver = selenium_setup()
    results: list[dict] = []
    seen_product_urls: set[str] = set()
    try:
        for url in discover_category_urls(driver):
            category = category_label(url)
            for row in parse_url(URL=url, category=category, driver=driver):
                if row.get("product_url") in seen_product_urls:
                    continue
                seen_product_urls.add(row["product_url"])
                results.append(row)
    finally:
        driver.quit()
    return results
