"""Shopify storefront JSON scraper base class.

Most modern Shopify storefronts expose a public ``/products.json`` endpoint
that returns paginated product data without any JS rendering.  This base
class iterates pages, expands variants into rows, and produces records
matching the gardens4you schema.

Each variant becomes its own row when a product has multiple non-trivial
variants (size options).  Products with only a single ``"Default Title"``
variant produce one row.

Subclasses override class attributes:

    source         — slug ("ballyrobert")
    base_url       — root URL ("https://www.ballyrobertgardens.com")
    currency       — "EUR" / "GBP" / etc.

That's typically all that's needed.  Subclasses can override
``parse_record`` for site-specific tweaks.
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
_DEFAULT_VARIANT_TITLE = "Default Title"


def _strip_html(html: str | None) -> str | None:
    if not html:
        return None
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", unescape(text)).strip()
    return text or None


def _parse_price(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


class ShopifyJsonScraper(BaseScraper):
    """Base class for Shopify storefronts that expose /products.json."""

    base_url: str = ""
    currency: str = "EUR"
    page_size: int = 250
    max_pages: int = 50

    # Required abstract methods from BaseScraper are not used because we
    # override run().  We provide no-op implementations here so the ABC is
    # satisfied.

    def discover_categories(self) -> list[tuple[str, str]]:  # noqa: D401
        return [(f"{self.base_url}/products.json", "all")]

    def parse_listing(self, html: str) -> list[str]:  # noqa: D401
        del html
        return []

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:  # noqa: D401
        del html, product_url, source_url, category
        return None

    def fetch_products_json(self, page: int) -> list[dict]:
        """Fetch one page of /products.json. Returns the products list."""
        url = f"{self.base_url}/products.json?limit={self.page_size}&page={page}"
        body = self.fetch(url)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return []
        return list(data.get("products", []))

    def parse_record(
        self, product: dict, variant: dict, source_url: str
    ) -> dict | None:
        """Build a single record from a (product, variant) pair.

        Subclasses may override to add site-specific fields or filtering.
        Returns None to drop.
        """
        product_url = f"{self.base_url}/products/{product['handle']}"
        variant_title = (variant.get("title") or "").strip()
        size = variant_title if variant_title and variant_title != _DEFAULT_VARIANT_TITLE else None

        images = product.get("images") or []
        img_url = images[0].get("src") if images else None

        price = _parse_price(variant.get("price"))
        if price is None:
            return None

        stock = 1 if variant.get("available") else 0
        category = product.get("product_type") or None

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": category,
            "product_name_raw": product.get("title") or "",
            "img_url": img_url,
            "description": _strip_html(product.get("body_html")),
            "price_native": price,
            "currency": self.currency,
            "size": size,
            "stock": stock,
            "product_code": variant.get("sku") or None,
        }

    def run(self) -> list[dict]:
        """Iterate /products.json pages, expand variants, return records."""
        results: list[dict] = []
        source_url = f"{self.base_url}/products.json"

        for page in range(1, self.max_pages + 1):
            try:
                products = self.fetch_products_json(page)
            except RetryExhausted as e:
                self.log.error("products_json_fetch_failed", page=page, error=str(e))
                self.report.error_count += 1
                break

            if not products:
                break

            self.log.info("products_json_page", page=page, products=len(products))

            for product in products:
                variants = product.get("variants") or []
                if not variants:
                    self.report.products_in += 1
                    self._drop("no_variants")
                    continue

                for variant in variants:
                    self.report.products_in += 1
                    try:
                        record = self.parse_record(product, variant, source_url)
                    except Exception as e:  # noqa: BLE001
                        self.log.warning(
                            "parse_record_failed",
                            handle=product.get("handle"),
                            error=str(e),
                        )
                        self._drop("parse_error")
                        continue

                    if record is None:
                        self._drop("parse_returned_none")
                        continue

                    results.append(record)
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
