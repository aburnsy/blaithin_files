"""DutchGrown scraper — NL bulb specialist, Shopify, EUR.

Per research: €11.99 < €100; FREE over €100.  Shopify exposes
/products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class DutchGrownScraper(ShopifyJsonScraper):
    source = "dutchgrown"
    base_url = "https://www.dutchgrown.eu"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with DutchGrownScraper() as scraper:
        return scraper.run()
