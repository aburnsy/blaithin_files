"""Newlands Garden Centre scraper — Dublin Shopify storefront, EUR.

Full-range garden centre; David Austin reseller; aquatics specialist.
Shopify exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class NewlandsScraper(ShopifyJsonScraper):
    source = "newlands"
    base_url = "https://www.newlands.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with NewlandsScraper() as scraper:
        return scraper.run()
