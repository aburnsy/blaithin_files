"""Hedges & Trees Direct scraper — Irish WooCommerce, EUR.

Per research: nationwide hedging and trees from €0.80/whitethorn.
Uses the WooCommerce Store API.
"""

from __future__ import annotations

from src.scrapers.woocommerce_store import WooStoreApiScraper


class HedgesDirectScraper(WooStoreApiScraper):
    source = "hedges_direct"
    base_url = "https://hedgesandtreesdirect.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with HedgesDirectScraper() as scraper:
        return scraper.run()
