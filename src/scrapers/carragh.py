"""Caragh Nurseries scraper — WooCommerce, no JS rendering needed.

Caragh's product pages use WooCommerce's variable-product pattern: the
full per-variation pricing/stock data is embedded as a JSON blob on the
``<form class="variations_form">`` element via the
``data-product_variations`` attribute. We read it straight from the
static HTML — no Selenium, no dropdown iteration, no stale-element
exceptions.

For non-variable products we read the single price/stock from the
WooCommerce price span / ``.stock`` element.
"""

from __future__ import annotations

import html as _htmllib
import importlib
import json
import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.http import RetryExhausted

_BASE = "https://caraghnurseries.ie"


class CaraghScraper(BaseScraper):
    source = "carragh"
    rate_limit_seconds = 1.0

    def __init__(self, config_module: str = "config.carragh"):
        super().__init__()
        self._config = importlib.import_module(config_module)

    def discover_categories(self) -> list[tuple[str, str]]:
        """Walk each configured category, paginating ``/page/<n>/`` until empty."""
        leaves: list[tuple[str, str]] = []
        for base_url, category_name in self._config.data_sources:
            page = 1
            while True:
                url = base_url if page == 1 else f"{base_url.rstrip('/')}/page/{page}/"
                listing_html = self._safe_fetch(url)
                if not listing_html or not self._listing_has_products(listing_html):
                    break
                leaves.append((url, category_name))
                page += 1
        return leaves

    def _safe_fetch(self, url: str) -> str:
        try:
            return self.fetch(url)
        except RetryExhausted as e:
            # 404 past last page is expected; quiet log + stop pagination.
            if "404" in str(e):
                self.log.debug("pagination_end", url=url)
                return ""
            self.log.warning("listing_fetch_failed", url=url, error=str(e))
            return ""

    @staticmethod
    def _listing_has_products(html: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        return bool(
            soup.find("ul", class_=re.compile(r"\bproducts\b"))
            and soup.find("li", class_=re.compile(r"\bproduct\b"))
        )

    def parse_listing(self, html: str) -> list[str]:
        """Return deduplicated product URLs from a Carragh category page."""
        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        unique: list[str] = []
        for a in soup.find_all("a", href=True):
            href = _as_str(a.get("href"))
            if not href:
                continue
            if "caraghnurseries.ie/product/" in href and "product-category" not in href:
                url = re.sub(r"^https?://(?:www\.)?caraghnurseries\.ie", _BASE, href)
                # Canonical product URLs have a trailing slash; without it
                # every fetch eats a 301 round-trip. Normalise then re-append.
                url = url.split("?", 1)[0].rstrip("/") + "/"
                if url == f"{_BASE}/product/vouchers/":
                    continue
                if url not in seen:
                    seen.add(url)
                    unique.append(url)
        return unique

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | list[dict] | None:
        soup = BeautifulSoup(html, "html.parser")

        product_name = self._extract_product_name(soup)
        if not product_name:
            return None

        description = self._extract_description(soup)
        default_image = self._extract_default_image(soup)

        # Variable product? Read every variant from data-product_variations.
        variants = self._extract_variations(soup)
        if variants:
            return [
                {
                    "source": self.source,
                    "source_url": source_url,
                    "product_url": product_url,
                    "category": category,
                    "product_name": product_name,
                    "img_url": v.get("img_url") or default_image,
                    "description": description,
                    "price": v.get("price"),
                    "size": v.get("size"),
                    "stock": v.get("stock"),
                }
                for v in variants
            ]

        # Simple product — single price/stock.
        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": category,
            "product_name": product_name,
            "img_url": default_image,
            "description": description,
            "price": self._extract_simple_price(soup),
            "size": self._extract_simple_size(soup, product_name),
            "stock": self._extract_simple_stock(soup),
        }

    # ------------------------------------------------------------------
    # WooCommerce extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_product_name(soup: BeautifulSoup) -> str | None:
        for sel in (".product_title.entry-title", "h1.product_title", "h1"):
            el = soup.select_one(sel)
            if el:
                name = el.get_text(strip=True)
                if name:
                    return name
        return None

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        # Short description (above-the-fold) is preferred for matching.
        short = soup.select_one(".woocommerce-product-details__short-description")
        if short:
            text = short.get_text(" ", strip=True)
            if text:
                return text
        long_desc = soup.select_one("#tab-description") or soup.select_one(
            ".woocommerce-Tabs-panel--description"
        )
        if long_desc:
            text = long_desc.get_text(" ", strip=True)
            if text:
                return text
        return None

    @staticmethod
    def _extract_default_image(soup: BeautifulSoup) -> str | None:
        img = soup.select_one(".woocommerce-product-gallery__image img")
        if not img:
            return None
        for key in ("src", "data-large_image", "data-src"):
            val = _as_str(img.get(key))
            if val:
                return val
        srcset = _as_str(img.get("srcset"))
        if srcset:
            return srcset.split(" ", 1)[0]
        return None

    def _extract_variations(self, soup: BeautifulSoup) -> list[dict]:
        """Read WooCommerce's per-variation JSON from the form's data attribute."""
        form = soup.find("form", class_=re.compile(r"\bvariations_form\b"))
        if not form:
            return []
        raw = _as_str(form.get("data-product_variations"))
        if not raw:
            return []
        # WooCommerce HTML-escapes the JSON inside the attribute value
        # (e.g. &quot; for ", &amp; for &). Decode before parsing.
        try:
            data = json.loads(_htmllib.unescape(raw))
        except json.JSONDecodeError as e:
            self.log.warning("variations_json_parse_failed", error=str(e))
            return []
        if not isinstance(data, list):
            return []

        out: list[dict] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            out.append(
                {
                    "price": _to_float(entry.get("display_price")),
                    "size": _pick_size_attribute(entry.get("attributes")),
                    "stock": _variant_stock(entry),
                    "img_url": _variant_image(entry.get("image")),
                }
            )
        return out

    @staticmethod
    def _extract_simple_price(soup: BeautifulSoup) -> float | None:
        bdi = soup.select_one("p.price .woocommerce-Price-amount bdi") or soup.select_one(
            ".woocommerce-Price-amount bdi"
        )
        if not bdi:
            return None
        text = bdi.get_text(strip=True)
        cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
        parts = cleaned.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = parts[0].replace(".", "") + "." + parts[1]
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    @staticmethod
    def _extract_simple_stock(soup: BeautifulSoup) -> int | None:
        out_el = soup.select_one("p.stock.out-of-stock, .stock.out-of-stock")
        if out_el:
            return 0
        in_el = soup.select_one("p.stock.in-stock, .stock.in-stock")
        if in_el:
            text = in_el.get_text(strip=True)
            m = re.search(r"(\d+)", text)
            return int(m.group(1)) if m else 1
        return None

    @staticmethod
    def _extract_simple_size(soup: BeautifulSoup, product_name: str) -> str | None:
        # Look in the "additional information" table for a pot size row.
        for row in soup.select(
            "table.shop_attributes tr, table.woocommerce-product-attributes tr"
        ):
            label_el = row.find("th")
            value_el = row.find("td")
            if not (label_el and value_el):
                continue
            label = label_el.get_text(strip=True).lower()
            if "pot" in label or "size" in label:
                value = value_el.get_text(strip=True)
                if value:
                    return value
        # Fallback: size-looking substring in the product name (e.g. "18L").
        m = re.search(r"\b\d+\s*(?:L|cm|m)\b", product_name)
        return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Module-level helpers (testable without instantiating the scraper)
# ---------------------------------------------------------------------------


def _as_str(v) -> str | None:
    """BeautifulSoup attribute getters can return list/None — normalise to str|None."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v:
        first = v[0]
        return first if isinstance(first, str) else None
    return None


def _to_float(v) -> float | None:
    try:
        return float(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None


def _pick_size_attribute(attrs) -> str | None:
    """Pick the most size-like attribute value from a WooCommerce variation dict."""
    if not isinstance(attrs, dict):
        return None
    preferred: str | None = None
    fallback: str | None = None
    for k, v in attrs.items():
        if not v:
            continue
        val = str(v)
        key = str(k).lower()
        if "pot-size" in key or key.endswith("size"):
            preferred = val
            break
        if fallback is None:
            fallback = val
    return preferred or fallback


def _variant_stock(entry: dict) -> int | None:
    """Derive a stock count from a variation entry, mirroring WooCommerce semantics."""
    max_qty = entry.get("max_qty")
    if isinstance(max_qty, (int, float)) and max_qty:
        return int(max_qty)
    is_in_stock = entry.get("is_in_stock")
    if is_in_stock is True:
        return 1
    if is_in_stock is False:
        return 0
    return None


def _variant_image(image) -> str | None:
    if not isinstance(image, dict):
        return None
    for key in ("src", "full_src", "thumb_src"):
        val = image.get(key)
        if isinstance(val, str) and val:
            return val
    return None


# ---------------------------------------------------------------------------
# Backward-compat shim — load_bronze_data.py calls get_product_data()
# ---------------------------------------------------------------------------


def get_product_data(config_file_name: str = "carragh") -> list[dict]:
    """Backward-compat shim — runs the new scraper and returns the legacy list."""
    with CaraghScraper(config_module=f"config.{config_file_name}") as scraper:
        return scraper.run()
