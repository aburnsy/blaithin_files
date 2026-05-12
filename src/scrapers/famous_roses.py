"""Famous Roses World scraper — Romania/EU rose specialist, Shopify, EUR.

Per research: bare-root + potted roses; ships across EU including IE.
Shopify exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class FamousRosesScraper(ShopifyJsonScraper):
    source = "famous_roses"
    base_url = "https://en.famousroses.eu"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with FamousRosesScraper() as scraper:
        return scraper.run()
