"""J Parker's (IE) scraper — BigCommerce Stencil with custom theme.

J Parker's PDPs do not expose the standard ``span.price--withTax`` element;
instead the price lives in a ``<meta property="product:price:amount">`` tag
and on ``section.productView-data`` as ``data-price``. The listing markup is
``ul.productGrid > li.product > a.card-wrapper`` (no ``.card-title a`` like
QuickCrop). Single-price products are the norm — no variant resolution
needed against ``/remote/v1/product-attributes``.
"""

from __future__ import annotations

import importlib
import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.http import RetryExhausted

_BASE = "https://www.jparkers.com"


class JParkersScraper(BaseScraper):
    source = "jparkers"
    rate_limit_seconds = 0.6

    def __init__(self, config_module: str = "config.jparkers"):
        super().__init__()
        self._config = importlib.import_module(config_module)

    def discover_categories(self) -> list[tuple[str, str]]:
        leaves: list[tuple[str, str]] = []
        for base_url, category_name in self._config.data_sources:
            page = 1
            while True:
                url = base_url if page == 1 else f"{base_url}?page={page}"
                html = self._safe_fetch(url)
                if not html or not self._listing_has_grid(html):
                    break
                leaves.append((url, category_name))
                page += 1
        return leaves

    def _safe_fetch(self, url: str) -> str:
        try:
            return self.fetch(url)
        except RetryExhausted as e:
            self.log.warning("listing_fetch_failed", url=url, error=str(e))
            return ""

    @staticmethod
    def _listing_has_grid(html: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        return bool(soup.select_one("ul.productGrid li.product a.card-wrapper"))

    def parse_listing(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[str] = []
        seen: set[str] = set()
        for a in soup.select("ul.productGrid li.product a.card-wrapper[href]"):
            href = _as_str(a.get("href"))
            if not href:
                continue
            url = re.sub(r"^https?://(?:www\.)?jparkers\.com", _BASE, href).split("?", 1)[0]
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        data = soup.select_one("section.productView-data")
        if data is None:
            return None

        product_name = _as_str(data.get("data-name")) or self._fallback_name(soup)
        if not product_name:
            return None

        price = _price_from_text(_as_str(data.get("data-price")) or "")
        if price is None:
            meta = soup.find("meta", attrs={"property": "product:price:amount"})
            if meta is not None:
                price = _price_from_text(_as_str(meta.get("content")) or "")

        img_url = self._extract_image(soup)
        description = self._extract_description(soup)
        size = self._extract_size(soup)

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": category,
            "product_name": product_name,
            "img_url": img_url,
            "description": description,
            "price": price,
            "size": size,
            "stock": None,
            "quantity": 1,
        }

    @staticmethod
    def _fallback_name(soup: BeautifulSoup) -> str | None:
        h1 = soup.select_one("h1.productView-title, h1")
        return h1.get_text(strip=True) if h1 else None

    @staticmethod
    def _extract_image(soup: BeautifulSoup) -> str | None:
        img = soup.select_one(".productView-img-container img, .productView-image img")
        if not img:
            return None
        return _as_str(img.get("src")) or _as_str(img.get("data-src"))

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        # The PDP has no rich description; the accordion section under the
        # gallery carries the substantive content (Key Points / Plant Size /
        # Planting Notes / Soil Type). Use that as the description.
        sect = soup.select_one("section.productView-accordions")
        if sect is None:
            meta = soup.find("meta", attrs={"property": "og:description"})
            return _as_str(meta.get("content")) if meta else None
        text = sect.get_text(" ", strip=True)
        return text or None

    @staticmethod
    def _extract_size(soup: BeautifulSoup) -> str | None:
        # Listing cards expose "How Supplied:" lines (e.g. "Top-grade Tubers",
        # "Bare Root"). On the PDP this lives in the productView-options
        # block under a span.value if present.
        for label in soup.find_all(string=re.compile(r"How Supplied", re.IGNORECASE)):
            parent = label.find_parent()
            if not parent:
                continue
            # Look for sibling text after the label
            sib = parent.find_next_sibling()
            if sib:
                t = sib.get_text(" ", strip=True)
                if t:
                    return t
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v:
        first = v[0]
        return first if isinstance(first, str) else None
    return None


def _price_from_text(text: str) -> float | None:
    cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    parts = cleaned.rsplit(".", 1)
    if len(parts) == 2 and len(parts[1]) <= 2:
        cleaned = parts[0].replace(".", "") + "." + parts[1]
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def get_product_data(config_file_name: str = "jparkers") -> list[dict]:
    with JParkersScraper(config_module=f"config.{config_file_name}") as scraper:
        return scraper.run()
