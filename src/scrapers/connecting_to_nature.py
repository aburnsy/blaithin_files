"""Connecting to Nature scraper — Shopify storefront, EUR.

Waterford native wildflower / bird-food / hedging shop.  Sixth-generation
family business.  Shopify exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class ConnectingToNatureScraper(ShopifyJsonScraper):
    source = "connecting_to_nature"
    base_url = "https://connectingtonature.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with ConnectingToNatureScraper() as scraper:
        return scraper.run()
