"""Mid Ulster Garden Centre scraper — NI Shopify, GBP.

NI nursery; ships UK + Ireland.  Useful as a T&M seed proxy for IE
customers per research.  Shopify exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class MidUlsterScraper(ShopifyJsonScraper):
    source = "mid_ulster"
    base_url = "https://midulster.co.uk"
    currency = "GBP"


def get_product_data() -> list[dict]:
    with MidUlsterScraper() as scraper:
        return scraper.run()
