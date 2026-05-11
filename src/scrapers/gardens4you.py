"""Gardens4You scraper — Magento-style site, no JS rendering needed."""

from __future__ import annotations

import importlib
import re
from typing import Optional

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper

_size_pattern_cm = re.compile(r"\d+\s*cm", re.IGNORECASE)
_size_pattern_litre = re.compile(r"\d+\s*ltr", re.IGNORECASE)
_size_pattern_pval = re.compile(r"P\s*\d+")
_stock_pattern = re.compile(r"\d+")


class Gardens4YouScraper(BaseScraper):
    source = "gardens4you"
    rate_limit_seconds = 1.0

    def __init__(self, config_module: str = "config.gardens4you"):
        super().__init__()
        self._config = importlib.import_module(config_module)

    def discover_categories(self) -> list[tuple[str, str]]:
        return list(self._config.data_sources)

    def parse_listing(self, html: str) -> list[str]:
        """Return deduplicated list of product page URLs from a category listing."""
        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        unique: list[str] = []
        for a in soup.find_all("a", class_="product-item-link", href=True):
            href: str = a["href"]
            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                url = f"https://www.gardens4you.ie{href}"
            else:
                continue
            if url not in seen:
                seen.add(url)
                unique.append(url)
        # Fallback: regex match on aNNNN.html pattern (catches sites with slight class variation)
        if not unique:
            for href in re.findall(r'href="([^"]+a\d+\.html)"', html):
                url = href if href.startswith("http") else f"https://www.gardens4you.ie{href}"
                if url not in seen:
                    seen.add(url)
                    unique.append(url)
        return unique

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> Optional[dict]:
        """Parse a product page. Returns a dict or None to drop (never raises)."""
        soup = BeautifulSoup(html, "html.parser")

        # Product name — required; if missing this is not a real product page
        name_el = soup.find("h1")
        if not name_el:
            return None
        product_name = name_el.get_text(strip=True)
        if not product_name:
            return None

        # Price — prefer data-price-amount attribute (exact float), fall back to span text
        price = self._extract_price(soup)

        # Size — nullable; try product attributes first, then name; no fake fallbacks
        size = self._extract_size(soup, product_name)

        # Stock — best-effort integer; None if not found
        stock = self._extract_stock(soup)

        # Image
        img_el = soup.find("img", class_=re.compile(r"product"))
        img_url = img_el.get("src") if img_el else None

        # Description
        desc_el = soup.find("div", class_="product attribute description")
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
    def _extract_price(soup: BeautifulSoup) -> Optional[float]:
        # Most reliable: data-price-amount attribute on the main product price widget
        el = soup.find(attrs={"data-price-amount": True})
        if el:
            try:
                return float(el["data-price-amount"])
            except (ValueError, TypeError):
                pass
        # Fallback: first span.price
        price_span = soup.select_one("span.price")
        if price_span:
            text = price_span.get_text(strip=True)
            m = re.search(r"(\d+[.,]\d+|\d+)", text.replace(",", "."))
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    @staticmethod
    def _extract_size(soup: BeautifulSoup, product_name: str) -> Optional[str]:
        """Extract pot/height size from product attribute divs or product name.

        Returns None if no size signal found — caller must treat size as optional.
        Previously the legacy code raised Exception or returned 'Bare Root' as a
        silent fallback; both behaviours are removed.
        """
        # Check Magento product attribute divs first (most reliable)
        for div in soup.find_all("div", class_=re.compile(r"product attribute")):
            text = div.get_text(strip=True)
            # "Nursery pot size 9cm" / "Delivered as bare root" etc.
            if "pot size" in text.lower() or "nursery" in text.lower():
                m = re.search(_size_pattern_cm, text)
                if m:
                    return m.group(0)
            if "root" in text.lower() or "bare" in text.lower():
                return "Bare Root"
            if "seed" in text.lower():
                return "Seeds"
            # Generic cm match in an attribute div
            m = re.search(_size_pattern_cm, text)
            if m:
                return m.group(0)

        # Fall back to product name
        if m := re.search(_size_pattern_cm, product_name):
            return m.group(0)
        if m := re.search(_size_pattern_litre, product_name):
            return m.group(0).replace("tr", "")
        if m := re.search(_size_pattern_pval, product_name):
            return m.group(0)
        if "bare root" in product_name.lower():
            return "Bare Root"

        return None  # Unknown — let caller handle as nullable

    @staticmethod
    def _extract_stock(soup: BeautifulSoup) -> Optional[int]:
        """Return stock count or None."""
        stock_span = soup.find("span", class_=re.compile(r"amstockstatus"))
        if stock_span:
            text = stock_span.get_text(strip=True)
            # "Stock 100+" -> 100  |  "Out of stock" -> 0
            if "out of stock" in text.lower():
                return 0
            m = re.search(_stock_pattern, text)
            if m:
                return int(m.group(0))
        return None


# ---------------------------------------------------------------------------
# Backward-compat shim — load_bronze_data.py calls get_product_data()
# ---------------------------------------------------------------------------

def get_product_data(config_file_name: str = "gardens4you") -> list[dict]:
    """Backward-compat shim — runs the new scraper and returns the legacy list."""
    with Gardens4YouScraper(config_module=f"config.{config_file_name}") as scraper:
        return scraper.run()
