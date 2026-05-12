"""Hopeless Botanics scraper — Dublin houseplant Shopify, EUR."""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class HopelessBotanicsScraper(ShopifyJsonScraper):
    source = "hopeless_botanics"
    base_url = "https://hopelessbotanics.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with HopelessBotanicsScraper() as scraper:
        return scraper.run()
