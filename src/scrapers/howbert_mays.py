"""Howbert & Mays scraper — Dublin Shopify storefront, EUR.

Three-shop Dublin garden / homeware retailer; premium tier (Biohort, etc).
Shopify exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class HowbertMaysScraper(ShopifyJsonScraper):
    source = "howbert_mays"
    base_url = "https://howbertandmays.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with HowbertMaysScraper() as scraper:
        return scraper.run()
