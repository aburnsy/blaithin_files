"""Mount Venus Nursery scraper — Dublin WooCommerce, EUR.

Specialist perennials (Dublin 16); mail order Oct–Apr.  Uses the
WooCommerce Store API.
"""

from __future__ import annotations

from src.scrapers.woocommerce_store import WooStoreApiScraper


class MountVenusScraper(WooStoreApiScraper):
    source = "mount_venus"
    base_url = "https://mountvenusnursery.com"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with MountVenusScraper() as scraper:
        return scraper.run()
