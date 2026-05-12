"""WooCommerce Store API scraper base class.

Modern WooCommerce installs expose ``/wp-json/wc/store/v1/products`` —
a public, paginated JSON endpoint that the storefront blocks themselves
use.  No auth required, no JS rendering, no HTML parsing.

Subclasses just override ``source``, ``base_url`` and ``currency``.
"""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from src.scrapers.base import BaseScraper
from src.scrapers.http import RetryExhausted

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str | None) -> str | None:
    if not html:
        return None
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", unescape(text)).strip()
    return text or None


def _parse_price(raw: Any, minor_unit: int) -> float | None:
    """WooCommerce returns prices as strings in the smallest currency unit."""
    if raw is None or raw == "":
        return None
    try:
        return float(raw) / (10 ** minor_unit)
    except (ValueError, TypeError):
        return None


class WooStoreApiScraper(BaseScraper):
    """Base class for WooCommerce sites exposing /wp-json/wc/store/v1/products."""

    base_url: str = ""
    currency: str = "EUR"
    page_size: int = 100
    max_pages: int = 50

    def discover_categories(self) -> list[tuple[str, str]]:  # noqa: D401
        return [(f"{self.base_url}/wp-json/wc/store/v1/products", "all")]

    def parse_listing(self, html: str) -> list[str]:  # noqa: D401
        del html
        return []

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:  # noqa: D401
        del html, product_url, source_url, category
        return None

    def fetch_products(self, page: int) -> list[dict]:
        url = (
            f"{self.base_url}/wp-json/wc/store/v1/products"
            f"?per_page={self.page_size}&page={page}"
        )
        body = self.fetch(url)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.get("products", []))
        return []

    def parse_record(self, product: dict, source_url: str) -> dict | None:
        """Build a single record from a WooCommerce Store-API product entry."""
        prices = product.get("prices") or {}
        minor_unit = int(prices.get("currency_minor_unit") or 2)
        price = _parse_price(prices.get("price"), minor_unit)
        if price is None:
            return None

        images = product.get("images") or []
        img_url = images[0].get("src") if images else None

        categories = product.get("categories") or []
        category = categories[0]["name"] if categories else None

        attributes = product.get("attributes") or []
        size: str | None = None
        for attr in attributes:
            name = (attr.get("name") or "").lower()
            if "size" in name or "pot" in name or "height" in name:
                terms = attr.get("terms") or []
                if terms:
                    size = terms[0].get("name")
                    break

        stock_avail = product.get("is_in_stock")
        stock = 1 if stock_avail else 0 if stock_avail is False else None

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product.get("permalink") or "",
            "category": category,
            "product_name_raw": unescape(product.get("name") or ""),
            "img_url": img_url,
            "description": _strip_html(product.get("short_description"))
            or _strip_html(product.get("description")),
            "price_native": price,
            "currency": self.currency,
            "size": size,
            "stock": stock,
            "product_code": product.get("sku") or None,
        }

    def run(self) -> list[dict]:
        results: list[dict] = []
        source_url = f"{self.base_url}/wp-json/wc/store/v1/products"
        for page in range(1, self.max_pages + 1):
            try:
                products = self.fetch_products(page)
            except RetryExhausted as e:
                self.log.error("woo_fetch_failed", page=page, error=str(e))
                self.report.error_count += 1
                break
            if not products:
                break
            self.log.info("woo_page", page=page, products=len(products))
            for product in products:
                self.report.products_in += 1
                try:
                    rec = self.parse_record(product, source_url)
                except Exception as e:  # noqa: BLE001
                    self.log.warning("parse_record_failed", id=product.get("id"), error=str(e))
                    self._drop("parse_error")
                    continue
                if rec is None:
                    self._drop("parse_returned_none")
                    continue
                results.append(rec)
                self.report.products_parsed += 1
        self.log.info(
            "scrape_complete",
            source=self.source,
            in_=self.report.products_in,
            parsed=self.report.products_parsed,
            dropped=self.report.dropped,
            errors=self.report.error_count,
        )
        return results
