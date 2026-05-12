"""Fluwel scraper — NL premium-bulb Shopify storefront, EUR.

Per research: premium large-size bulbs; €33.25 flat to IE.  Shopify
exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class FluwelScraper(ShopifyJsonScraper):
    source = "fluwel"
    base_url = "https://www.fluwel.com"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with FluwelScraper() as scraper:
        return scraper.run()
