"""David Austin Roses (EU) scraper — Shopify storefront.

CRITICAL: Uses https://eu.davidaustinroses.com — the .com domain does NOT
ship to Ireland. Only the .eu domain works. Per sub-project R research.

Coverage strategy: Shopify's public ``/products.json`` returns every
product in the catalog, paginated. The legacy scraper walked a
hand-picked subset of collection URLs and missed everything outside
those 7 collections — see [[full-coverage]] memory. The full-catalog
JSON endpoint is the right primitive.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class DavidAustinScraper(ShopifyJsonScraper):
    source = "david_austin"
    base_url = "https://eu.davidaustinroses.com"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with DavidAustinScraper() as scraper:
        return scraper.run()
