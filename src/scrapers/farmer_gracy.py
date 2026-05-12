"""Farmer Gracy scraper — UK→NL Shopify bulb specialist, GBP.

Packs in NL and ships across the EU including ROI per research.
Shopify exposes /products.json publicly on the `.co.uk` domain.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class FarmerGracyScraper(ShopifyJsonScraper):
    source = "farmer_gracy"
    base_url = "https://www.farmergracy.co.uk"
    currency = "GBP"


def get_product_data() -> list[dict]:
    with FarmerGracyScraper() as scraper:
        return scraper.run()
