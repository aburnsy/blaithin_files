"""Future Forests scraper — West Cork Shopify storefront, EUR.

Per research: trees / hedging / fruit / ornamentals; €15–€75 zoned ship.
Shopify exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class FutureForestsScraper(ShopifyJsonScraper):
    source = "future_forests"
    base_url = "https://futureforests.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with FutureForestsScraper() as scraper:
        return scraper.run()
