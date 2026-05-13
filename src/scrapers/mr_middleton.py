"""Mr Middleton scraper — BigCommerce Stencil, Halo theme.

Same backbone as QuickcropScraper (BigCommerce Stencil). The only
differences are the listing markup (Halo theme uses ``article.card``
cards rather than ``ul.productGrid > li``) and the description block
on PDPs (``#tab-description`` instead of QuickCrop's custom block).

Category discovery is sitemap-driven for full coverage: every
``<loc>`` in ``/xmlsitemap.php?type=categories`` is walked. The base
class' config-driven seed list is bypassed.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.scrapers.quickcrop import QuickcropScraper, _as_str

_BASE = "https://www.mrmiddleton.com"


class MrMiddletonScraper(QuickcropScraper):
    source = "mr_middleton"
    rate_limit_seconds = 0.6
    _site_base = _BASE

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
    def _extract_description(soup: BeautifulSoup) -> str | None:
        tab = soup.select_one("#tab-description")
        if tab is None:
            return None
        # Skip the "Description" header at the top of the tab.
        for h in tab.find_all(["h1", "h2", "h3"]):
            h.decompose()
        text = tab.get_text(" ", strip=True)
        return text or None


def get_product_data() -> list[dict]:
    with MrMiddletonScraper() as scraper:
        return scraper.run()
