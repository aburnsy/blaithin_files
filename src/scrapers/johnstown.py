"""Johnstown Garden Centre scraper — Kildare full-range on Magento 2, EUR.

Excellent €4.75 flat shipping anywhere in IE & NI. Stocks Suttons & Thompson
& Morgan seeds that are otherwise blocked direct-to-ROI post-Brexit.
"""

from __future__ import annotations

from src.scrapers.magento_graphql import MagentoGraphQLScraper


class JohnstownScraper(MagentoGraphQLScraper):
    source = "johnstown"
    base_url = "https://johnstowngardencentre.ie"
    currency = "EUR"
    # Johnstown's Magento returns 500 when stock_status is included in the
    # products() projection. Disabling drops stock info but keeps the
    # 4715-product catalogue accessible.
    include_stock_status = False


def get_product_data() -> list[dict]:
    with JohnstownScraper() as scraper:
        return scraper.run()
