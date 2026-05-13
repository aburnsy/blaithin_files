"""Dutch-Bulbs.com scraper — NL bulb specialist on Magento 2, EUR.

Spring-flowering bulbs, perennials, shrubs. Tiered shipping to IE: €8.95 under
€50, €5.95 €50-99, free €100+. Canonical host is dutch-bulbs.com (no www);
the www variant 301s to root.
"""

from __future__ import annotations

from src.scrapers.magento_graphql import MagentoGraphQLScraper


class DutchBulbsScraper(MagentoGraphQLScraper):
    source = "dutch_bulbs"
    base_url = "https://dutch-bulbs.com"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with DutchBulbsScraper() as scraper:
        return scraper.run()
