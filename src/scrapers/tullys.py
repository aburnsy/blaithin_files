"""Tully Nurseries scraper — rewritten for the new Blazor Server SPA.

The legacy ASP.NET Web Forms shop at shop.tullynurseries.ie was replaced
with a Blazor Server "Web Portal" (Herbst Software). All product data
streams over a SignalR WebSocket, so HTTP-only scraping yields an empty
shell. We drive a headless Chrome via Selenium, wait for Blazor to
render, then parse the resulting DOM with BeautifulSoup.

Architecture
------------
- discover_leaves(): walk the category tree starting from `/`. Each card
  exposes an `<a class="stretched-link" href="c/<CODE>">` overlay. We
  recurse until a page has product cards instead of sub-category cards.
- scrape_leaf(): paginate `/c/<CODE>?page=N` (96 cards per full page)
  until fewer than 96 are returned. Every field we need (name, code,
  stock, price, size, image, product URL) is on the listing card, so
  we don't need to fetch each product page.

Schema matches the legacy scraper for compatibility with
load_bronze_data.py and downstream matching.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

_BASE = "https://shop.tullynurseries.ie"
_PAGE_SIZE = 96
_MAX_PAGES = 50


def _make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)


def _wait_for(driver: webdriver.Chrome, css: str, timeout: int = 20) -> bool:
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css))
        )
        return True
    except TimeoutException:
        return False


def _is_leaf(soup: BeautifulSoup) -> bool:
    """A page is a leaf (product listing) when it contains product-code spans."""
    return bool(soup.select("div.card.h-100 span.font-monospace small"))


def _category_links(soup: BeautifulSoup) -> list[str]:
    """Sub-category hrefs ('c/<CODE>') from branch pages."""
    out: list[str] = []
    for a in soup.select('a.stretched-link[href^="c/"]'):
        href = a.get("href")
        if isinstance(href, str):
            out.append(href)
    return out


def _category_name(soup: BeautifulSoup) -> str:
    """Best-effort: take the heading text immediately following the breadcrumb."""
    for sel in ("h1", "h2", "h3"):
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return ""


def _extract_price(card_text: str) -> tuple[float | None, str | None]:
    """The card splits '€7.92/2 Litre' across text nodes (€ | 7.92 | /2 Litre);
    we operate on the whole card text and let the regex skip whitespace/newlines."""
    m = re.search(r"€\s*([\d.,]+)\s*/?\s*([^\n€]*)", card_text)
    if not m:
        return None, None
    try:
        price = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, None
    size = m.group(2).strip() or None
    return price, size


def _parse_card(card, source_url: str, category: str) -> dict | None:
    name_a = card.select_one("a.fw-semibold")
    code_el = card.select_one("span.font-monospace small")
    if not name_a or not code_el:
        return None

    name = name_a.get_text(strip=True)
    href = name_a.get("href", "")
    product_url = urljoin(_BASE + "/", href) if href else None
    code = code_el.get_text(strip=True)

    stock = 0
    stock_el = card.select_one(
        "span[class*='border-success'], span[class*='border-warning'], "
        "span[class*='border-danger']"
    )
    if stock_el:
        m = re.search(r"\d+", stock_el.get_text())
        if m:
            stock = int(m.group())

    price, size = _extract_price(card.get_text(" "))

    img_el = card.select_one("img.card-img-top")
    img_src = img_el.get("src") if img_el else None
    img_url = urljoin(_BASE + "/", img_src) if img_src else None

    return {
        "source": "tullys",
        "source_url": source_url,
        "product_url": product_url,
        "category": category,
        "product_name": name,
        "product_code": code,
        "img_url": img_url,
        "description": None,
        "price": price,
        "size": size,
        "stock": stock,
    }


def _load_page(driver: webdriver.Chrome, url: str) -> BeautifulSoup | None:
    """Navigate and wait for Blazor to render either product cards or sub-cats.

    Blazor swaps the page contents in two steps over SignalR: structure first,
    then values. We poll for card-count stability so we don't grab a frame
    where the previous page's cards are still on screen.
    """
    driver.get(url)
    rendered = _wait_for(
        driver,
        "div.card.h-100 span.font-monospace small, a.stretched-link[href^='c/']",
        timeout=20,
    )
    if not rendered:
        return None

    # Poll for DOM stability — same card count for two consecutive 500ms reads.
    prev_signature = ""
    for _ in range(20):
        time.sleep(0.5)
        cards = driver.find_elements(By.CSS_SELECTOR, "div.card.h-100")
        codes = driver.find_elements(
            By.CSS_SELECTOR, "div.card.h-100 span.font-monospace small"
        )
        signature = f"{len(cards)}|{len(codes)}|"
        if codes:
            try:
                signature += (codes[0].text or "") + "|" + (codes[-1].text or "")
            except Exception:  # noqa: BLE001
                pass
        if signature == prev_signature and signature != "0|0|":
            break
        prev_signature = signature

    return BeautifulSoup(driver.page_source, "html.parser")


def _discover_leaves(driver: webdriver.Chrome) -> list[tuple[str, str]]:
    """Walk the category tree. Returns [(absolute_url, category_path), ...]."""
    visited: set[str] = set()
    leaves: list[tuple[str, str]] = []
    queue: list[tuple[str, str]] = [(_BASE + "/", "")]

    while queue:
        url, parent_path = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        soup = _load_page(driver, url)
        if soup is None:
            continue

        if _is_leaf(soup):
            name = _category_name(soup) or parent_path or url.rsplit("/", 1)[-1]
            leaves.append((url, name))
            continue

        # Branch — enqueue every sub-category overlay
        for href in _category_links(soup):
            sub_url = urljoin(_BASE + "/", href)
            if sub_url in visited:
                continue
            heading = _category_name(soup) or parent_path
            queue.append((sub_url, heading))

    return leaves


def _scrape_leaf(
    driver: webdriver.Chrome, url: str, category: str
) -> list[dict]:
    products: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        page_url = url if page == 1 else f"{url}?page={page}"
        soup = _load_page(driver, page_url)
        if soup is None or not _is_leaf(soup):
            break

        page_products = []
        for card in soup.select("div.card.h-100"):
            record = _parse_card(card, source_url=url, category=category)
            if record is not None:
                page_products.append(record)

        if not page_products:
            break
        products.extend(page_products)
        if len(page_products) < _PAGE_SIZE:
            break
    return products


def get_product_data(config_file_name: str = "tullys") -> list[dict]:
    """Entry point used by load_bronze_data.py."""
    driver = _make_driver()
    try:
        leaves = _discover_leaves(driver)
        print(f"Discovered {len(leaves)} leaf categories")
        all_products: list[dict] = []
        for url, category in leaves:
            print(f"Scraping {category} ({url})")
            try:
                rows = _scrape_leaf(driver, url, category)
            except WebDriverException as e:
                print(f"  Failed {url}: {e}")
                continue
            print(f"  -> {len(rows)} products")
            all_products.extend(rows)
        return all_products
    finally:
        driver.quit()
