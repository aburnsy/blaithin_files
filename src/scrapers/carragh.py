"""Caragh Nurseries scraper — WooCommerce, full catalog via Store API.

Switched from hand-picked category seeds + HTML scraping to the public
``/wp-json/wc/store/v1/products`` endpoint, which returns every product
in the catalog with variations, stock, and pricing in JSON. See
[[full-coverage]] memory.
"""

from __future__ import annotations

from src.scrapers.woocommerce_store import WooStoreApiScraper


class CaraghScraper(WooStoreApiScraper):
    source = "carragh"
    base_url = "https://caraghnurseries.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with CaraghScraper() as scraper:
        return scraper.run()
