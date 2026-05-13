"""GreenGardenFlowerBulbs.nl scraper — NL B2B bulb wholesaler on Magento 2.

Prices are listed ex-VAT (B2B portal); the storage layer applies 23% IE VAT
at bronze-write time. €500 minimum order applies — relevant for landscapers
and large garden installs.
"""

from __future__ import annotations

from src.scrapers.magento_graphql import MagentoGraphQLScraper


class GreenGardenFlowerBulbsScraper(MagentoGraphQLScraper):
    source = "greengardenflowerbulbs"
    base_url = "https://www.greengardenflowerbulbs.nl"
    currency = "EUR"


def get_product_data() -> list[dict]:
    with GreenGardenFlowerBulbsScraper() as scraper:
        return scraper.run()
