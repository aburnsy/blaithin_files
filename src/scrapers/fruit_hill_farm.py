"""Fruit Hill Farm scraper — Bantry Magento 2, EUR.

Largest IE organic seed-potato range plus garlic, onion sets, organic flower
bulbs and propagation supplies. Standard Magento /graphql endpoint serves the
catalogue without auth.
"""

from __future__ import annotations

from src.scrapers.magento_graphql import MagentoGraphQLScraper


class FruitHillFarmScraper(MagentoGraphQLScraper):
    source = "fruit_hill_farm"
    base_url = "https://www.fruithillfarm.com"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with FruitHillFarmScraper() as scraper:
        return scraper.run()
