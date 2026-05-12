"""Ballyrobert Gardens scraper — NI Shopify storefront, ships ROI in GBP.

Per sub-project R research: £5.99 flat, free over £200.  Shopify exposes
/products.json publicly.  See src.scrapers.shopify_json for the shared
base class.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class BallyrobertScraper(ShopifyJsonScraper):
    source = "ballyrobert"
    base_url = "https://www.ballyrobertgardens.com"
    currency = "GBP"


def get_product_data() -> list[dict]:
    """Backward-compat shim — runs the scraper and returns a list of dicts."""
    with BallyrobertScraper() as scraper:
        return scraper.run()
