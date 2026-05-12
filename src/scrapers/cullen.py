"""Cullen Nurseries scraper — Carlow WooCommerce, EUR.

DAFM-approved native trees + hedging specialist.  Uses the WooCommerce
Store API.
"""

from __future__ import annotations

from src.scrapers.woocommerce_store import WooStoreApiScraper


class CullenScraper(WooStoreApiScraper):
    source = "cullen"
    base_url = "https://cullennurseries.ie"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with CullenScraper() as scraper:
        return scraper.run()
