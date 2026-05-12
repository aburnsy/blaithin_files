"""Plant Store scraper — Irish indoor-plant Shopify, EUR."""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class PlantStoreScraper(ShopifyJsonScraper):
    source = "plant_store"
    base_url = "https://www.plantstore.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with PlantStoreScraper() as scraper:
        return scraper.run()
