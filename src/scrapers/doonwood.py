"""Doonwood Nurseries scraper — Galway WooCommerce, EUR.

Native, fruit, ornamental, flowering trees + bare-root & potted hedging.
Standard /wp-json/wc/store/v1/products endpoint.
"""

from __future__ import annotations

from src.scrapers.woocommerce_store import WooStoreApiScraper


class DoonwoodScraper(WooStoreApiScraper):
    source = "doonwood"
    base_url = "https://doonwood.com"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with DoonwoodScraper() as scraper:
        return scraper.run()
