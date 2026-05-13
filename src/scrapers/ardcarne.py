"""Ardcarne Garden Centre scraper — sitemap-driven HTML.

Custom Cloudflare-fronted platform (no GraphQL). The site responds to a
plain httpx GET with a Chrome User-Agent, no JS rendering required. Walk
``/sitemap.xml`` to discover every ``/product/<id>/<slug>`` URL, then fetch
each one and extract from schema.org microdata + breadcrumbs.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.http import build_client

_BASE = "https://www.ardcarne.ie"
_SITEMAP = f"{_BASE}/sitemap.xml"
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class ArdcarneScraper(BaseScraper):
    source = "ardcarne"
    rate_limit_seconds = 0.4

    def __enter__(self):
        # Override to send a Chrome-style UA — Cloudflare blocks the default
        # bot UA on some hosts. Plain GETs still work; no JS rendering.
        self._client = build_client(
            rate_limit_seconds=self.rate_limit_seconds,
            user_agent=_CHROME_UA,
        )
        return self

    def discover_categories(self) -> list[tuple[str, str]]:
        """Return [(sitemap_url, "sitemap")] — single seed to drive ``run()``."""
        return [(_SITEMAP, "sitemap")]

    def parse_listing(self, html: str) -> list[str]:
        """Extract all /product/<id>/<slug> URLs from sitemap XML."""
        urls = re.findall(r"<loc>([^<]+)</loc>", html)
        out: list[str] = []
        seen: set[str] = set()
        for u in urls:
            if "/product/" not in u:
                continue
            # Normalise — strip query string + trailing slash
            url = u.split("?", 1)[0].rstrip("/")
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")

        product_name = self._extract_name(soup)
        if not product_name:
            return None

        price = self._extract_price(soup)
        if price is None:
            return None  # unpriced products (POA / enquiry-only) — drop

        breadcrumb = self._extract_breadcrumbs(soup)
        # Skip leading "Home" and "Products" labels — take the deepest concrete
        # section as the category. Falls back to "" if no useful crumb exists.
        cat = ""
        for c in breadcrumb:
            if c and c.lower() not in ("home", "products"):
                cat = c
        if not cat:
            cat = category

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": cat,
            "product_name": product_name,
            "img_url": self._extract_image(soup),
            "description": self._extract_description(soup),
            "price": price,
            "size": None,
            "stock": self._extract_stock(soup),
            "quantity": 1,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _extract_name(soup: BeautifulSoup) -> str | None:
        h1 = soup.find("h1")
        if h1:
            t = h1.get_text(strip=True)
            if t:
                return t
        og = soup.find("meta", attrs={"property": "og:title"})
        if og:
            content = og.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None

    @staticmethod
    def _extract_price(soup: BeautifulSoup) -> float | None:
        meta = soup.find("meta", attrs={"itemprop": "price"})
        if meta is None:
            return None
        raw = meta.get("content")
        if not isinstance(raw, str):
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _extract_breadcrumbs(soup: BeautifulSoup) -> list[str]:
        crumbs: list[str] = []
        for span in soup.select('[itemprop=item] span[itemprop=name]'):
            t = span.get_text(strip=True)
            if t:
                crumbs.append(t)
        return crumbs

    @staticmethod
    def _extract_image(soup: BeautifulSoup) -> str | None:
        og = soup.find("meta", attrs={"property": "og:image"})
        if og is not None:
            content = og.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        # tab-8 is the product-info tab carrying long-form copy on most PDPs.
        tab = soup.select_one("div.product-tab.tab-8")
        if tab is not None:
            t = tab.get_text(" ", strip=True)
            if t:
                return t
        og = soup.find("meta", attrs={"property": "og:description"})
        if og is not None:
            content = og.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None

    @staticmethod
    def _extract_stock(soup: BeautifulSoup) -> int | None:
        link = soup.find("link", attrs={"itemprop": "availability"})
        if link is None:
            return None
        href = link.get("href")
        if not isinstance(href, str):
            return None
        if href.endswith("/InStock"):
            return 1
        if href.endswith("/OutOfStock"):
            return 0
        return None


def get_product_data() -> list[dict]:
    with ArdcarneScraper() as scraper:
        return scraper.run()
