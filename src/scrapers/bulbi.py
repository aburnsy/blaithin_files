"""Bulbi.nl scraper — NL bulb specialist on Magento 2, EUR.

Prices listed include VAT per their T&Cs (Art. 5: "Alle prijzen zijn vermeld
in euro's, inclusief BTW en exclusief verzendkosten"). Driven via the
public Magento GraphQL endpoint — no JS, no credentials.
"""

from __future__ import annotations

from src.scrapers.magento_graphql import MagentoGraphQLScraper


class BulbiScraper(MagentoGraphQLScraper):
    source = "bulbi"
    base_url = "https://www.bulbi.nl"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with BulbiScraper() as scraper:
        return scraper.run()
