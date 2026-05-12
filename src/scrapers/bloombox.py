"""Bloombox Club (Ireland) scraper — Shopify, EUR.

Subscription-box-and-houseplant retailer; .ie storefront uses EUR
pricing (verified via JSON-LD priceCurrency on a product page).
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class BloomboxScraper(ShopifyJsonScraper):
    source = "bloombox"
    base_url = "https://bloomboxclub.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with BloomboxScraper() as scraper:
        return scraper.run()
