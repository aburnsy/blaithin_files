"""PlantGift.ie scraper — Irish Shopify storefront, EUR.

Family-run Dublin shop sourcing from EU growers; free shipping across IE
+ 24 EU countries per research.  Shopify exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class PlantGiftScraper(ShopifyJsonScraper):
    source = "plantgift"
    base_url = "https://plantgift.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with PlantGiftScraper() as scraper:
        return scraper.run()
