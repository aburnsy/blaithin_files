"""Hedging.ie scraper — WooCommerce site, free delivery to Ireland.

Identified in sub-project R research as top value pick for free shipping.
Site uses WooCommerce with variable products (size attributes).
Price is extracted from JSON-LD structured data (AggregateOffer).
Stock status is read from .stock span or JSON-LD availability.
"""

from __future__ import annotations

import importlib
import json
import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper

_BASE = "https://hedging.ie"

_SCHEMA_AVAILABILITY_IN_STOCK = "https://schema.org/InStock"


class HedgingIeScraper(BaseScraper):
    source = "hedgingie"
    rate_limit_seconds = 1.0

    def __init__(self, config_module: str = "config.hedgingie"):
        super().__init__()
        self._config = importlib.import_module(config_module)

    def discover_categories(self) -> list[tuple[str, str]]:
        return list(self._config.data_sources)

    def parse_listing(self, html: str) -> list[str]:
        """Return deduplicated list of product page URLs from a WooCommerce category page."""
        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        unique: list[str] = []
        for a in soup.find_all("a", href=True):
            href: str = a["href"]
            # Normalise to https://hedging.ie (site sometimes emits http:// links)
            if "hedging.ie/product/" in href and "product-category" not in href:
                url = re.sub(r"^https?://(?:www\.)?hedging\.ie", _BASE, href)
                if url not in seen:
                    seen.add(url)
                    unique.append(url)
        return unique

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        """Parse a WooCommerce product page. Returns a dict or None to drop."""
        soup = BeautifulSoup(html, "html.parser")

        # Product name — prefer WooCommerce product_title class (avoids sidebar H1s)
        name_el = soup.select_one(".product_title.entry-title")
        if not name_el:
            # Fallback: h1 inside <main>
            main = soup.find("main")
            name_el = main.find("h1") if main else None
        if not name_el:
            return None
        product_name = name_el.get_text(strip=True)
        if not product_name:
            return None

        # Price + stock — extract from JSON-LD (most reliable for variable products)
        price, in_stock = self._extract_price_and_stock_from_ld(soup)

        # Fallback price from WooCommerce price span
        if price is None:
            price = self._extract_price_from_html(soup)

        # Fallback stock from .stock element
        if in_stock is None:
            in_stock = self._extract_stock_from_html(soup)

        stock = 1 if in_stock else (0 if in_stock is False else None)

        # Size — from the attribute_pa_size select (WooCommerce variation attribute)
        size = self._extract_size(soup)

        # Image — WooCommerce product gallery
        img_el = soup.select_one(".woocommerce-product-gallery__image img")
        img_url = None
        if img_el:
            img_url = img_el.get("src") or img_el.get("data-src")

        # Short description
        desc_el = soup.select_one(".woocommerce-product-details__short-description")
        description = desc_el.get_text(strip=True) if desc_el else None

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
    def _extract_price_and_stock_from_ld(
        soup: BeautifulSoup,
    ) -> tuple[float | None, bool | None]:
        """Extract lowest price and in-stock flag from JSON-LD AggregateOffer / Offer."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            graph = data.get("@graph", [data])
            for item in graph:
                if "Product" not in str(item.get("@type", "")):
                    continue
                offers = item.get("offers")
                if not offers:
                    continue
                if isinstance(offers, dict):
                    offers = [offers]
                if not isinstance(offers, list):
                    continue
                first = offers[0]
                # AggregateOffer uses lowPrice; plain Offer uses price
                raw_price = first.get("lowPrice") or first.get("price")
                try:
                    price = float(raw_price) if raw_price is not None else None
                except (ValueError, TypeError):
                    price = None
                availability = first.get("availability", "")
                in_stock: bool | None = None
                if availability:
                    in_stock = _SCHEMA_AVAILABILITY_IN_STOCK in availability
                return price, in_stock
        return None, None

    @staticmethod
    def _extract_price_from_html(soup: BeautifulSoup) -> float | None:
        """Fallback: parse first .woocommerce-Price-amount bdi text."""
        bdi = soup.select_one(".woocommerce-Price-amount bdi")
        if not bdi:
            return None
        text = bdi.get_text(strip=True)
        # Strip currency symbols (€, £, etc.) and whitespace; handle thousands separator
        cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
        # If multiple dots, keep only the last decimal
        parts = cleaned.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = parts[0].replace(".", "") + "." + parts[1]
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    @staticmethod
    def _extract_stock_from_html(soup: BeautifulSoup) -> bool | None:
        """Read WooCommerce .stock span for in/out-of-stock."""
        out_el = soup.select_one(".stock.out-of-stock")
        if out_el:
            return False
        in_el = soup.select_one(".stock.in-stock")
        if in_el:
            return True
        return None

    @staticmethod
    def _extract_size(soup: BeautifulSoup) -> str | None:
        """Return the first non-empty size option label from the WooCommerce variation select."""
        size_select = soup.find("select", attrs={"name": re.compile(r"attribute_pa_size")})
        if not size_select:
            return None
        options = [
            o.get_text(strip=True)
            for o in size_select.find_all("option")
            if o.get("value")  # skip blank placeholder option
        ]
        return options[0] if options else None


# ---------------------------------------------------------------------------
# Backward-compat shim — load_bronze_data.py calls get_product_data()
# ---------------------------------------------------------------------------


def get_product_data(config_file_name: str = "hedgingie") -> list[dict]:
    """Backward-compat shim — runs the new scraper and returns the legacy list."""
    with HedgingIeScraper(config_module=f"config.{config_file_name}") as scraper:
        return scraper.run()
