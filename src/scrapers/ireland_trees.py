"""Ireland Trees (Kearney's Nursery) scraper — Limerick Shopify storefront, EUR.

Native trees, bare-root hedging, fruit & ornamental trees. Standard Shopify
/products.json works without anti-bot.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class IrelandTreesScraper(ShopifyJsonScraper):
    source = "ireland_trees"
    base_url = "https://www.irelandtrees.com"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with IrelandTreesScraper() as scraper:
        return scraper.run()
