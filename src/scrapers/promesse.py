"""Promesse de Fleurs (IE) scraper — paginated Magento 2 HTML listing.

The Magento ``/graphql`` endpoint 500s on every ``products(...)`` shape, so we
walk the ``/all-plants.html`` master listing instead. Each listing page renders
49 product cards with name, URL, price, image, stock and a "from" price for
products with variants. That's enough for the matching pipeline — we don't
fetch per-product pages (would balloon to ~26k requests for the same data
already on the listing).

Magento clamps invalid page numbers back to page 1, so the loop stops when
the first product ID on a page repeats the first ID from page 1.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.http import RetryExhausted, build_client

_BASE = "https://www.promessedefleurs.ie"
_LISTING = f"{_BASE}/all-plants.html"
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_MAX_PAGES = 700  # hard ceiling; the natural stop is the wraparound sentinel.


class PromesseScraper(BaseScraper):
    source = "promesse"
    rate_limit_seconds = 0.5

    def __enter__(self):
        self._client = build_client(
            rate_limit_seconds=self.rate_limit_seconds,
            user_agent=_CHROME_UA,
        )
        return self

    # The BaseScraper hooks below are required by the ABC but unused — we
    # override run() because each listing page IS the data, no per-product
    # fetch is needed.
    def discover_categories(self) -> list[tuple[str, str]]:
        return [(_LISTING, "Plants")]

    def parse_listing(self, html: str) -> list[str]:
        return []

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        return None

    def run(self) -> list[dict]:
        results: list[dict] = []
        first_page_sentinel: str | None = None

        for page in range(1, _MAX_PAGES + 1):
            url = _LISTING if page == 1 else f"{_LISTING}?p={page}"
            try:
                html = self.fetch(url)
            except RetryExhausted as e:
                self.log.error("listing_fetch_failed", url=url, error=str(e))
                self.report.error_count += 1
                break

            cards = _extract_cards(html)
            if not cards:
                break

            page_sentinel = cards[0].get("product_id")
            if page == 1:
                first_page_sentinel = page_sentinel
            elif page_sentinel == first_page_sentinel:
                # Magento wrapped past the last page — stop.
                break

            for raw in cards:
                self.report.products_in += 1
                record = self._record_from_card(raw, source_url=url)
                if record is None:
                    self.report.dropped["parse_returned_none"] = (
                        self.report.dropped.get("parse_returned_none", 0) + 1
                    )
                    continue
                results.append(record)
                self.report.products_parsed += 1

        self.log.info(
            "scrape_complete",
            source=self.source,
            in_=self.report.products_in,
            parsed=self.report.products_parsed,
            dropped=self.report.dropped,
            errors=self.report.error_count,
        )
        return results

    def _record_from_card(self, card: dict, *, source_url: str) -> dict | None:
        if not card.get("product_name") or card.get("product_url") is None:
            return None
        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": card["product_url"],
            "category": _category_from_url(card["product_url"]),
            "product_name": card["product_name"],
            "img_url": card.get("img_url"),
            "description": None,
            "price": card.get("price"),
            "size": card.get("size"),
            "stock": card.get("stock"),
            "quantity": 1,
        }


# ---------------------------------------------------------------------------
# HTML extraction helpers (module-level so tests can call them directly)
# ---------------------------------------------------------------------------


def _extract_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for el in soup.select(".product-item"):
        pid = el.get("data-product-id")
        a = el.select_one("a.product-item-link")
        if a is None:
            continue
        href = a.get("href")
        name = a.get("title") or a.get_text(" ", strip=True)
        if not href or not name:
            continue
        if not isinstance(href, str) or not isinstance(name, str):
            continue
        img = el.select_one("img")
        img_url = img.get("src") if img else None
        if not isinstance(img_url, str):
            img_url = None
        price_span = el.select_one(".price-box span.price")
        price = _price_from_text(price_span.get_text(strip=True)) if price_span else None
        stock = _stock_from_card(el)
        size = _size_from_card(el)
        out.append(
            {
                "product_id": pid if isinstance(pid, str) else None,
                "product_name": name.strip(),
                "product_url": href.split("?", 1)[0],
                "img_url": img_url,
                "price": price,
                "stock": stock,
                "size": size,
            }
        )
    return out


def _category_from_url(url: str) -> str:
    """Top-level category from the product URL path.

    /annuals/flower-seeds/.../foo.html -> "Annuals"
    /perennials/foo.html -> "Perennials"
    """
    path = url.replace(_BASE, "", 1).lstrip("/")
    first = path.split("/", 1)[0].rsplit(".", 1)[0]
    if not first:
        return ""
    return first.replace("-", " ").title()


def _price_from_text(text: str) -> float | None:
    cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    parts = cleaned.rsplit(".", 1)
    if len(parts) == 2 and len(parts[1]) <= 2:
        cleaned = parts[0].replace(".", "") + "." + parts[1]
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _stock_from_card(el) -> int | None:
    box = el.select_one(".stock-status")
    if box is None:
        return None
    raw = box.get_text(" ", strip=True)
    if not raw:
        return None
    m = re.search(r"(\d+)", raw)
    if m:
        return int(m.group(1))
    low = raw.lower()
    if "out of stock" in low or "unavailable" in low:
        return 0
    return None


def _size_from_card(el) -> str | None:
    sz = el.select_one(".product-sizes")
    if sz is None:
        return None
    raw = sz.get_text(" ", strip=True)
    m = re.search(r"Available in (\d+)\s*size", raw, re.IGNORECASE)
    if m and m.group(1) != "1":
        return f"{m.group(1)} sizes"
    return None


def get_product_data() -> list[dict]:
    with PromesseScraper() as scraper:
        return scraper.run()
