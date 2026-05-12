"""Beattys of Loughrea scraper — hardware/garden Shopify, EUR.

Per research: free over €100 (excluding bulky).  Reseller of Suttons
and Thompson & Morgan **seeds** (UK-blocked retail brands).  Shopify
exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class BeattysScraper(ShopifyJsonScraper):
    source = "beattys"
    base_url = "https://www.beattys.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with BeattysScraper() as scraper:
        return scraper.run()
