"""Magento 2 GraphQL storefront scraper base class.

Magento 2 stores expose a public ``/graphql`` endpoint that the storefront
itself uses. The ``products`` query is unauthenticated for catalog data —
no token, no session, no JS rendering — and returns paginated product
records including price, stock, image, categories and variant SKUs.

Subclasses set ``source``, ``base_url`` and ``currency`` (and may override
``store_header`` if the site uses ``Store`` headers to switch currency or
storefront view). Variant resolution for configurable products is handled
automatically: each child variant emits its own row with its size and price.
"""

from __future__ import annotations

import json
import re
import time
from html import unescape
from typing import Any

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.scrapers.base import BaseScraper
from src.scrapers.http import RetryExhausted

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_LIST_QUERY_TEMPLATE = """
query Products($pageSize: Int!, $currentPage: Int!) {
  products(search: "", pageSize: $pageSize, currentPage: $currentPage) {
    total_count
    page_info { current_page page_size total_pages }
    items {
      __typename
      sku
      name
      url_key
      __ITEM_STOCK__
      categories { name }
      image { url }
      short_description { html }
      price_range {
        minimum_price { final_price { value currency } }
      }
      ... on ConfigurableProduct {
        variants {
          product {
            sku
            name
            __VARIANT_STOCK__
            price_range { minimum_price { final_price { value currency } } }
          }
          attributes { code label }
        }
      }
    }
  }
}
""".strip()


def _build_list_query(*, include_stock: bool) -> str:
    stock = "stock_status" if include_stock else ""
    return (
        _LIST_QUERY_TEMPLATE
        .replace("__ITEM_STOCK__", stock)
        .replace("__VARIANT_STOCK__", stock)
    )


def _strip_html(html: str | None) -> str | None:
    if not html:
        return None
    text = _TAG_RE.sub(" ", html)
    text = _WS_RE.sub(" ", unescape(text)).strip()
    return text or None


def _coerce_price(node: Any) -> tuple[float | None, str | None]:
    if not isinstance(node, dict):
        return None, None
    fp = (node.get("minimum_price") or {}).get("final_price") or {}
    val = fp.get("value")
    cur = fp.get("currency")
    if isinstance(val, (int, float)):
        return float(val), cur if isinstance(cur, str) else None
    return None, cur if isinstance(cur, str) else None


def _variant_size(attributes: list[dict]) -> str | None:
    if not attributes:
        return None
    for attr in attributes:
        code = (attr.get("code") or "").lower()
        if any(k in code for k in ("size", "pack", "weight", "volume", "height")):
            label = attr.get("label")
            if isinstance(label, str) and label.strip():
                return label.strip()
    label = attributes[0].get("label")
    return label.strip() if isinstance(label, str) and label.strip() else None


class MagentoGraphQLScraper(BaseScraper):
    """Base class for Magento 2 storefronts exposing /graphql."""

    base_url: str = ""
    currency: str = "EUR"
    page_size: int = 100
    max_pages: int = 200
    store_header: str | None = None  # e.g. "en" or "default" if multi-store
    # Some Magento 2 installs 500 on stock_status in the products() query.
    # Subclasses can disable to drop the field and accept null stock data.
    include_stock_status: bool = True

    def discover_categories(self) -> list[tuple[str, str]]:  # noqa: D401
        return [(f"{self.base_url}/graphql", "all")]

    def parse_listing(self, html: str) -> list[str]:  # noqa: D401
        del html
        return []

    def parse_product(  # noqa: D401
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        del html, product_url, source_url, category
        return None

    def _post_graphql(self, query: str, variables: dict) -> dict | None:
        if self._client is None:
            raise RuntimeError("Scraper used outside of `with` block")
        if self.rate_limit_seconds > 0:
            time.sleep(self.rate_limit_seconds)
        headers = {"Content-Type": "application/json"}
        if self.store_header:
            headers["Store"] = self.store_header
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_exponential(multiplier=1, min=1, max=15),
                retry=retry_if_exception_type(
                    (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError)
                ),
                reraise=True,
            ):
                with attempt:
                    response = self._client.post(
                        f"{self.base_url}/graphql",
                        json={"query": query, "variables": variables},
                        headers=headers,
                    )
                    response.raise_for_status()
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        return None
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as e:
            self.log.warning("graphql_request_failed", error=str(e))
            return None
        return None

    def fetch_products_page(self, page: int) -> tuple[list[dict], int | None]:
        query = _build_list_query(include_stock=self.include_stock_status)
        payload = self._post_graphql(query, {"pageSize": self.page_size, "currentPage": page})
        if not payload:
            return [], None
        data = (payload.get("data") or {}).get("products") or {}
        items = data.get("items") or []
        total_pages = ((data.get("page_info") or {}).get("total_pages"))
        if not isinstance(total_pages, int):
            total_pages = None
        return list(items), total_pages

    def product_url_for(self, item: dict) -> str:
        key = item.get("url_key") or ""
        suffix = ".html"  # Magento default product URL suffix; most stores keep it
        return f"{self.base_url}/{key}{suffix}" if key else self.base_url

    def parse_records(self, item: dict, source_url: str) -> list[dict]:
        """Build one or more rows from a single GraphQL product item."""
        name = (item.get("name") or "").strip()
        if not name:
            return []
        product_url = self.product_url_for(item)
        categories = item.get("categories") or []
        category = categories[0].get("name") if categories else None
        image = (item.get("image") or {}).get("url")
        description = _strip_html(((item.get("short_description") or {}).get("html")))
        stock_status = item.get("stock_status")
        in_stock = 1 if stock_status == "IN_STOCK" else 0 if stock_status else None

        rows: list[dict] = []
        variants = item.get("variants") or []
        if variants:
            for v in variants:
                vp = v.get("product") or {}
                price, _ = _coerce_price(vp.get("price_range"))
                if price is None:
                    continue
                v_stock_status = vp.get("stock_status")
                v_stock = 1 if v_stock_status == "IN_STOCK" else 0 if v_stock_status else None
                rows.append(
                    {
                        "source": self.source,
                        "source_url": source_url,
                        "product_url": product_url,
                        "category": category,
                        "product_name_raw": name,
                        "img_url": image,
                        "description": description,
                        "price_native": price,
                        "currency": self.currency,
                        "size": _variant_size(v.get("attributes") or []),
                        "stock": v_stock,
                        "product_code": vp.get("sku") or item.get("sku") or None,
                    }
                )
            if rows:
                return rows

        # Simple / bundle / fallback: emit a single row from the root price.
        price, _ = _coerce_price(item.get("price_range"))
        if price is None:
            return []
        rows.append(
            {
                "source": self.source,
                "source_url": source_url,
                "product_url": product_url,
                "category": category,
                "product_name_raw": name,
                "img_url": image,
                "description": description,
                "price_native": price,
                "currency": self.currency,
                "size": None,
                "stock": in_stock,
                "product_code": item.get("sku") or None,
            }
        )
        return rows

    def run(self) -> list[dict]:
        results: list[dict] = []
        source_url = f"{self.base_url}/graphql"
        total_pages_hint: int | None = None

        for page in range(1, self.max_pages + 1):
            try:
                items, total_pages = self.fetch_products_page(page)
            except RetryExhausted as e:
                self.log.error("graphql_fetch_failed", page=page, error=str(e))
                self.report.error_count += 1
                break

            if total_pages is not None and total_pages_hint is None:
                total_pages_hint = total_pages

            if not items:
                break

            self.log.info("graphql_page", page=page, products=len(items))
            for item in items:
                self.report.products_in += 1
                if not isinstance(item, dict):
                    # Some Magento installs return null entries in the items
                    # array for products the storefront can't render (deleted
                    # / disabled SKUs still in the index). Skip silently.
                    self._drop("null_item")
                    continue
                try:
                    rows = self.parse_records(item, source_url)
                except Exception as e:  # noqa: BLE001
                    self.log.warning("parse_record_failed", sku=item.get("sku"), error=str(e))
                    self._drop("parse_error")
                    continue
                if not rows:
                    self._drop("parse_returned_none")
                    continue
                results.extend(rows)
                self.report.products_parsed += len(rows)

            if total_pages_hint is not None and page >= total_pages_hint:
                break

        self.log.info(
            "scrape_complete",
            source=self.source,
            in_=self.report.products_in,
            parsed=self.report.products_parsed,
            dropped=self.report.dropped,
            errors=self.report.error_count,
        )
        return results
