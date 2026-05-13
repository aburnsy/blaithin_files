"""The Organic Centre scraper — Leitrim BigCommerce, EUR.

Charity / social enterprise selling organic seeds, seed potatoes, transplants,
books, and garden supplies. BigCommerce Stencil with classic Cornerstone
theme. Catalogue is small (~560 products) so we walk the products sitemap
(``/xmlsitemap.php?type=products``) and parse each PDP's JSON-LD Product
block, which carries name / image / price / availability cleanly.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.http import RetryExhausted, build_client

_BASE = "https://shop.theorganiccentre.ie"
_SITEMAP_INDEX = f"{_BASE}/xmlsitemap.php"
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class OrganicCentreScraper(BaseScraper):
    source = "organic_centre"
    rate_limit_seconds = 0.4

    def __enter__(self):
        # Default UA gets a polite reception on this BC store but Chrome UA is
        # safer if behaviour drifts.
        self._client = build_client(
            rate_limit_seconds=self.rate_limit_seconds,
            user_agent=_CHROME_UA,
        )
        return self

    def discover_categories(self) -> list[tuple[str, str]]:
        """Return every products sub-sitemap as a 'listing'."""
        try:
            index_xml = self.fetch(_SITEMAP_INDEX)
        except RetryExhausted as e:
            self.log.error("sitemap_index_fetch_failed", error=str(e))
            return []

        urls: list[tuple[str, str]] = []
        for loc in re.findall(r"<loc>([^<]+)</loc>", index_xml):
            decoded = loc.replace("&amp;", "&")
            if "type=products" in decoded:
                urls.append((decoded, "products"))
        if not urls:
            self.log.warning("no_products_sitemap", index=_SITEMAP_INDEX)
        return urls

    def parse_listing(self, html: str) -> list[str]:
        urls = re.findall(r"<loc>([^<]+)</loc>", html)
        out: list[str] = []
        seen: set[str] = set()
        for u in urls:
            url = u.split("?", 1)[0].rstrip("/")
            # Skip the sitemap's own self-reference and the homepage.
            if url == _BASE or url.endswith("xmlsitemap.php"):
                continue
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        ld = _find_product_jsonld(soup)
        if ld is None:
            return None

        name = ld.get("name")
        if not isinstance(name, str) or not name.strip():
            return None

        offers = ld.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if not isinstance(offers, dict):
            offers = {}

        price = _coerce_price(offers.get("price"))
        if price is None:
            return None

        availability = offers.get("availability") or ""
        stock: int | None
        if isinstance(availability, str) and availability.endswith("/InStock"):
            stock = 1
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
            # JSON-LD here is URL-encoded; decode for downstream matching.
            from urllib.parse import unquote
            description = unquote(description).strip() or None

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
            "product_code": None,
        }


# ---------------------------------------------------------------------------
# JSON-LD helpers
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
    with OrganicCentreScraper() as scraper:
        return scraper.run()
