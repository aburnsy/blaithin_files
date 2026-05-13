"""Esker Farm Daffodils scraper — Tyrone bulb specialist (Symphony Commerce),
GBP.

Specialist daffodil grower (standard, intermediate, miniature + other bulbs).
NI based but ships ROI £8-£15 by weight. Custom platform; no /products.json
or REST API. The site exposes a flat /sitemap.xml — product URLs are
two-segment paths like ``/<division>/<slug>`` (e.g. ``/div-2-y-o-r/terminator``);
single-segment paths are category pages. Product pages carry schema.org
microdata (itemprop="name"/"price"/"availability") which we parse directly.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.http import build_client

_BASE = "https://www.eskerfarmdaffodils.com"
_SITEMAP = f"{_BASE}/sitemap.xml"
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_SKIP_PREFIXES = ("pages/", "blog/", "policies/", "products/", "collections/")


class EskerDaffodilsScraper(BaseScraper):
    source = "esker_daffodils"
    rate_limit_seconds = 0.4

    def __enter__(self):
        self._client = build_client(
            rate_limit_seconds=self.rate_limit_seconds,
            user_agent=_CHROME_UA,
        )
        return self

    def discover_categories(self) -> list[tuple[str, str]]:
        return [(_SITEMAP, "sitemap")]

    def parse_listing(self, html: str) -> list[str]:
        urls = re.findall(r"<loc>([^<]+)</loc>", html)
        out: list[str] = []
        seen: set[str] = set()
        for u in urls:
            if not u.startswith(_BASE):
                continue
            path = urlparse(u).path.strip("/")
            if not path or any(path.startswith(p) for p in _SKIP_PREFIXES):
                continue
            # Two-segment paths are products: /<category>/<slug>
            if path.count("/") != 1:
                continue
            url = f"{_BASE}/{path}"
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")

        # itemprop="name" appears on schema.org breadcrumb <meta> tags too;
        # prefer the visible <h1> on the PDP, fall back to og:title.
        name_el = soup.find("h1", attrs={"itemprop": "name"}) or soup.find("h1")
        name: str | None
        if name_el is not None:
            name = name_el.get_text(strip=True) or None
        else:
            og = soup.find("meta", attrs={"property": "og:title"})
            content = og.get("content") if og is not None else None
            name = content.strip() if isinstance(content, str) and content.strip() else None
        if not name:
            return None

        # Same shape — the visible price <h2> carries content="<value>".
        price_el = soup.find(
            ["h1", "h2", "h3", "h4", "span", "div"], attrs={"itemprop": "price"}
        ) or soup.find(attrs={"itemprop": "price"})
        price = _coerce_price(price_el.get("content") if price_el is not None else None)
        if price is None and price_el is not None:
            price = _coerce_price(price_el.get_text(strip=True))
        if price is None:
            return None

        avail_el = soup.find("link", attrs={"itemprop": "availability"})
        href = avail_el.get("href") if avail_el is not None else None
        stock: int | None
        if isinstance(href, str) and href.endswith("/InStock"):
            stock = 1
        elif isinstance(href, str) and href.endswith("/OutOfStock"):
            stock = 0
        else:
            stock = None

        og_img = soup.find("meta", attrs={"property": "og:image"})
        img_url: str | None = None
        if og_img is not None:
            content = og_img.get("content")
            if isinstance(content, str) and content.strip():
                img_url = content.strip()

        og_desc = soup.find("meta", attrs={"property": "og:description"}) or soup.find(
            "meta", attrs={"name": "description"}
        )
        description: str | None = None
        if og_desc is not None:
            content = og_desc.get("content")
            if isinstance(content, str) and content.strip():
                description = content.strip()

        # Category derived from URL path (e.g. /div-2-y-o-r/terminator -> div-2-y-o-r).
        cat = urlparse(product_url).path.strip("/").split("/", 1)[0] or category

        code: str | None = None
        code_el = soup.find(attrs={"itemprop": "productID"})
        if code_el is not None:
            raw = code_el.get("content") or code_el.get_text(strip=True)
            if isinstance(raw, str) and raw.strip():
                code = raw.strip()

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": cat,
            "product_name_raw": name,
            "img_url": img_url,
            "description": description,
            "price_native": price,
            "currency": "GBP",
            "size": None,
            "stock": stock,
            "product_code": code,
        }


def _coerce_price(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        cleaned = re.sub(r"[^\d.]", "", raw)
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
    return None


def get_product_data() -> list[dict]:
    with EskerDaffodilsScraper() as scraper:
        return scraper.run()
