"""Brown Envelope Seeds scraper — Shopify storefront, EUR.

Organic open-pollinated veg/herb/grain seed from West Cork.  Per research:
free over EUR 50.  Shopify exposes /products.json publicly.
"""

from __future__ import annotations

from src.scrapers.shopify_json import ShopifyJsonScraper


class BrownEnvelopeScraper(ShopifyJsonScraper):
    source = "brown_envelope"
    base_url = "https://brownenvelopeseeds.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with BrownEnvelopeScraper() as scraper:
        return scraper.run()
