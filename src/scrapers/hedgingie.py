"""Hedging.ie scraper — WooCommerce site, free delivery to Ireland.

Identified in sub-project R research as top value pick for free shipping.
Site exposes the public WooCommerce Store API at
``/wp-json/wc/store/v1/products`` — full catalog, no JS rendering, no
hand-picked seeds. See [[full-coverage]] memory for rationale.
"""

from __future__ import annotations

from src.scrapers.woocommerce_store import WooStoreApiScraper


class HedgingIeScraper(WooStoreApiScraper):
    source = "hedgingie"
    base_url = "https://hedging.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with HedgingIeScraper() as scraper:
        return scraper.run()
