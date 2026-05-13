"""Irish Seed Savers Association scraper — Clare WooCommerce, EUR.

Heritage Irish apple trees (bare-root + potted), organic heirloom seeds, and
gift-shop items. WooCommerce shop lives under /shop/ rather than /, and the
REST API + AIOSEO sitemaps don't expose products, so we walk every
``/shop/product-category/...`` URL listed on /shop/ with WordPress /page/N/
pagination, collect ``/shop/product/<slug>/`` links, then parse each PDP's
JSON-LD Product block.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.http import RetryExhausted

_BASE = "https://irishseedsavers.ie"
_SHOP_INDEX = f"{_BASE}/shop/"
_MAX_PAGES = 30  # safety cap; leaf categories have <5 pages each

_CAT_RE = re.compile(r'href="(https://irishseedsavers\.ie/shop/product-category/[^"]+/)"')
_PRODUCT_RE = re.compile(r"(/shop/product/[a-z0-9][a-z0-9-]*/)", re.IGNORECASE)


class SeedSaversScraper(BaseScraper):
    source = "seed_savers"
    rate_limit_seconds = 0.4

    def discover_categories(self) -> list[tuple[str, str]]:
        """Return paginated category URLs, probing each page so we don't burn
        retries on speculative /page/N/ URLs that don't exist.

        We page eagerly here because BaseScraper.run() then fetches each one
        once more to extract listings — duplicating the request. Per-category
        cost is one extra GET per existing page (negligible at this catalog
        size; ~60 categories with <5 pages each).
        """
        try:
            index_html = self.fetch(_SHOP_INDEX)
        except RetryExhausted as e:
            self.log.error("shop_index_fetch_failed", error=str(e))
            return []

        categories: list[str] = []
        seen: set[str] = set()
        for m in _CAT_RE.finditer(index_html):
            url = m.group(1).rstrip("/")
            if url not in seen:
                seen.add(url)
                categories.append(url)
        self.log.info("seed_savers_categories", count=len(categories))

        listings: list[tuple[str, str]] = []
        for cat_url in categories:
            cat_name = cat_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
            for page in range(1, _MAX_PAGES + 1):
                page_url = cat_url + "/" if page == 1 else f"{cat_url}/page/{page}/"
                try:
                    html = self.fetch(page_url)
                except RetryExhausted:
                    break  # 404 / network error → end of pagination for this cat
                if not _PRODUCT_RE.search(html):
                    break
                listings.append((page_url, cat_name))
        return listings

    def parse_listing(self, html: str) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for m in _PRODUCT_RE.finditer(html):
            path = m.group(1).rstrip("/") + "/"
            url = f"{_BASE}{path}"
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        if "<title>Page not found" in html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        ld = _find_product_jsonld(soup)
        if ld is None:
            return None

        name = ld.get("name")
        if not isinstance(name, str) or not name.strip():
            return None

        offers = ld.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            offers = {}

        price = _coerce_price(offers.get("price") or offers.get("lowPrice"))
        if price is None:
            return None

        availability = offers.get("availability") or ""
        if isinstance(availability, str) and availability.endswith("/InStock"):
            stock: int | None = 1
        elif isinstance(availability, str) and availability.endswith("/OutOfStock"):
            stock = 0
        else:
            stock = None

        img = ld.get("image")
        if isinstance(img, list):
            img = img[0] if img else None
        img_url = img if isinstance(img, str) else None

        description = ld.get("description")
        if isinstance(description, str):
            description = description.strip() or None

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": category,
            "product_name_raw": name.strip(),
            "img_url": img_url,
            "description": description,
            "price_native": price,
            "currency": "EUR",
            "size": None,
            "stock": stock,
            "product_code": ld.get("sku") if isinstance(ld.get("sku"), str) else None,
        }


# ---------------------------------------------------------------------------
# JSON-LD helpers (shared shape with organic_centre)
# ---------------------------------------------------------------------------


def _find_product_jsonld(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _iter_ld_nodes(data):
            if isinstance(node, dict) and node.get("@type") == "Product":
                return node
    return None


def _iter_ld_nodes(data):
    if isinstance(data, list):
        for item in data:
            yield from _iter_ld_nodes(item)
        return
    if not isinstance(data, dict):
        return
    yield data
    graph = data.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            yield from _iter_ld_nodes(item)


def _coerce_price(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            return None
    return None


def get_product_data() -> list[dict]:
    with SeedSaversScraper() as scraper:
        return scraper.run()
