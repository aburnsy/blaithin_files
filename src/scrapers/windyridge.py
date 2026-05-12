"""Windyridge Garden Centre scraper — Dún Laoghaire Shopify, EUR."""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class WindyridgeScraper(ShopifyJsonScraper):
    source = "windyridge"
    base_url = "https://www.windyridgegardencentre.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with WindyridgeScraper() as scraper:
        return scraper.run()
