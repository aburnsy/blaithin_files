"""Mr Middleton scraper — BigCommerce Stencil, Halo theme.

Same backbone as QuickcropScraper (BigCommerce Stencil). The only
differences are the listing markup (Halo theme uses ``article.card``
cards rather than ``ul.productGrid > li``) and the description block
on PDPs (``#tab-description`` instead of QuickCrop's custom block).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.scrapers.quickcrop import QuickcropScraper, _as_str, _price_from_text

_BASE = "https://www.mrmiddleton.com"


class MrMiddletonScraper(QuickcropScraper):
    source = "mr_middleton"
    rate_limit_seconds = 0.6

    def __init__(self, config_module: str = "config.mr_middleton"):
        super().__init__(config_module=config_module)

    @staticmethod
    def _listing_has_grid(html: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        return bool(soup.select_one("article.card[data-product-id]"))

    def parse_listing(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[str] = []
        seen: set[str] = set()
        for card in soup.select("article.card[data-product-id]"):
            a = card.select_one("a.card-figure__link") or card.select_one("a[href]")
            if a is None:
                continue
            href = _as_str(a.get("href"))
            if not href:
                continue
            url = re.sub(r"^https?://(?:www\.)?mrmiddleton\.com", _BASE, href).split("?", 1)[0]
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    @staticmethod
    def _extract_page_price(soup: BeautifulSoup) -> float | None:
        # Some MM products display "€22.00 - €149.99" price ranges on the PDP.
        # quickcrop's _price_from_text strips separators and would parse
        # "2200149.99" — take the first price token instead.
        span = soup.find("span", class_="price price--withTax")
        if not span:
            return None
        raw = span.get_text(strip=True)
        m = re.search(r"(\d+(?:[.,]\d+)?)", raw)
        return _price_from_text(m.group(1)) if m else None

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        tab = soup.select_one("#tab-description")
        if tab is None:
            return None
        # Skip the "Description" header at the top of the tab.
        for h in tab.find_all(["h1", "h2", "h3"]):
            h.decompose()
        text = tab.get_text(" ", strip=True)
        return text or None


def get_product_data(config_file_name: str = "mr_middleton") -> list[dict]:
    with MrMiddletonScraper(config_module=f"config.{config_file_name}") as scraper:
        return scraper.run()
