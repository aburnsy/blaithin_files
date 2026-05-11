"""David Austin Roses (EU) scraper — Shopify site.

CRITICAL: Uses https://eu.davidaustinroses.com — the .com domain does NOT
ship to Ireland.  Only the .eu domain works.  Per sub-project R research.

Site is Shopify.  Product data comes reliably from JSON-LD (one <script
type="application/ld+json"> per product page with full Offer[] list including
price, variant name, availability and currency).  Listing pages use .product-card
divs with <a href="/products/<slug>"> inside.
"""

from __future__ import annotations

import importlib
import json
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper

_BASE = "https://eu.davidaustinroses.com"
_SCHEMA_IN_STOCK = "https://schema.org/InStock"


class DavidAustinScraper(BaseScraper):
    """Scraper for David Austin Roses EU (eu.davidaustinroses.com)."""

    source = "david_austin"
    rate_limit_seconds = 1.0

    def __init__(self, config_module: str = "config.david_austin"):
        super().__init__()
        self._config = importlib.import_module(config_module)

    def discover_categories(self) -> list[tuple[str, str]]:
        return list(self._config.data_sources)

    def parse_listing(self, html: str) -> list[str]:
        """Return deduplicated product page URLs from a Shopify collection page.

        Extracts /products/<slug> hrefs found inside .product-card divs.
        Falls back to a regex scan if no cards are found (future layout changes).
        Gift-card products are excluded.
        """
        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        unique: list[str] = []

        # Primary: anchors inside .product-card elements
        for card in soup.select(".product-card"):
            a = card.find("a", href=re.compile(r"^/products/"))
            if a:
                href: str = a["href"]
                url = urljoin(_BASE, href.split("?")[0])
                if url not in seen and "gift-card" not in url:
                    seen.add(url)
                    unique.append(url)

        # Fallback: regex scan for any /products/<slug> href
        if not unique:
            for href in re.findall(r'href="(/products/[^"?#]+)"', html):
                url = urljoin(_BASE, href)
                if url not in seen and "gift-card" not in url:
                    seen.add(url)
                    unique.append(url)

        return unique

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> Optional[dict]:
        """Parse a Shopify product page.  Returns a dict or None to drop.

        Extracts data primarily from JSON-LD structured data, which on David
        Austin's site contains a full Offer[] list with per-variant price,
        name (size) and availability.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Product name — from H1 (prefer page title over sidebar headings)
        name_el = soup.find("h1")
        if not name_el:
            return None
        product_name = name_el.get_text(strip=True)
        if not product_name:
            return None

        # Price, stock, size from JSON-LD
        price, in_stock, size = self._extract_from_ld(soup)

        # Fallback price from .money span (Shopify standard)
        if price is None:
            price = self._extract_price_from_html(soup)

        stock = 1 if in_stock else (0 if in_stock is False else None)

        # Image — og:image is most reliable on Shopify
        img_url = self._extract_image(soup)

        # Short description from JSON-LD description field already parsed, or
        # fall back to the meta description tag
        description = self._extract_description(soup)

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": category,
            "product_name_raw": product_name,
            "img_url": img_url,
            "description": description,
            "price_native": price,
            "currency": "EUR",
            "size": size,
            "stock": stock,
        }

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_from_ld(
        soup: BeautifulSoup,
    ) -> tuple[Optional[float], Optional[bool], Optional[str]]:
        """Extract lowest available price, in-stock flag, and variant/size name from JSON-LD.

        David Austin's JSON-LD uses an Offer[] list where each offer represents a
        variant (e.g. "Bare Root", "Potted").  We pick the lowest-priced in-stock
        offer; if nothing is in stock we take the lowest price regardless.
        """
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, list):
                data = data[0] if data else {}
            if "Product" not in str(data.get("@type", "")):
                continue

            offers = data.get("offers", [])
            if isinstance(offers, dict):
                offers = [offers]
            if not isinstance(offers, list) or not offers:
                continue

            # Collect all (price, in_stock, size_name) tuples
            parsed: list[tuple[float, bool, str]] = []
            for offer in offers:
                raw_price = offer.get("price") or offer.get("lowPrice")
                try:
                    p = float(raw_price) if raw_price is not None else None
                except (ValueError, TypeError):
                    p = None
                avail = offer.get("availability", "")
                is_in = _SCHEMA_IN_STOCK in avail if avail else None
                size_name: str = offer.get("name", "") or ""
                if p is not None:
                    parsed.append((p, bool(is_in), size_name))

            if not parsed:
                continue

            # Prefer in-stock offers; fallback to all offers
            in_stock_offers = [(p, s, n) for (p, s, n) in parsed if s]
            candidates = in_stock_offers if in_stock_offers else parsed
            best = min(candidates, key=lambda t: t[0])
            price, is_in_stock, size = best
            return price, (True if in_stock_offers else None), (size or None)

        return None, None, None

    @staticmethod
    def _extract_price_from_html(soup: BeautifulSoup) -> Optional[float]:
        """Fallback: parse first .money span on the page."""
        el = soup.select_one(".money")
        if not el:
            el = soup.select_one("[class*='price']")
        if not el:
            return None
        text = el.get_text(strip=True)
        cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
        # Handle thousands separators: if multiple dots keep last decimal
        parts = cleaned.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = parts[0].replace(".", "") + "." + parts[1]
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    @staticmethod
    def _extract_image(soup: BeautifulSoup) -> Optional[str]:
        """Return image URL from og:image meta tag (most reliable on Shopify)."""
        og = soup.find("meta", property="og:image")
        if og:
            return og.get("content")
        # Fallback: first product image
        img = soup.select_one(".product__media img, .product-single__photo img")
        if img:
            return img.get("src") or img.get("data-src")
        return None

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> Optional[str]:
        """Return description from meta description or product description div."""
        # JSON-LD description is most reliable but we already parsed the LD block;
        # use meta description as a quick fallback here.
        meta = soup.find("meta", attrs={"name": "description"})
        if meta:
            content = meta.get("content", "").strip()
            if content:
                return content
        desc_div = soup.select_one(".product__description, .product-single__description")
        if desc_div:
            return desc_div.get_text(strip=True) or None
        return None


# ---------------------------------------------------------------------------
# Backward-compat shim — load_bronze_data.py calls get_product_data()
# ---------------------------------------------------------------------------


def get_product_data(config_file_name: str = "david_austin") -> list[dict]:
    """Backward-compat shim — runs the new scraper and returns the legacy list."""
    with DavidAustinScraper(config_module=f"config.{config_file_name}") as scraper:
        return scraper.run()
