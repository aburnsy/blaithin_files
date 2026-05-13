"""J Parker's (IE) scraper — BigCommerce Stencil with custom theme.

J Parker's PDPs do not expose the standard ``span.price--withTax`` element;
instead the price lives in a ``<meta property="product:price:amount">`` tag
and on ``section.productView-data`` as ``data-price``. The listing markup is
``ul.productGrid > li.product > a.card-wrapper`` (no ``.card-title a`` like
QuickCrop). Single-price products are the norm — no variant resolution
needed against ``/remote/v1/product-attributes``.

Category discovery is sitemap-driven for full coverage: every
``<loc>`` in ``/xmlsitemap.php?type=categories`` is walked.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.bigcommerce_sitemap import bc_category_urls
from src.scrapers.concurrent import fetch_all_concurrent
from src.scrapers.http import RetryExhausted

_BASE = "https://www.jparkers.com"
_MAX_CONCURRENT = 10
_MAX_PAGES_PER_CATEGORY = 20


class JParkersScraper(BaseScraper):
    source = "jparkers"
    rate_limit_seconds = 0.0  # serial fetch unused; concurrent path below

    def discover_categories(self) -> list[tuple[str, str]]:
        """Hook kept for API compatibility — ``run()`` does its own
        concurrent discovery and ignores this output."""
        return []

    def _safe_fetch(self, url: str) -> str:
        try:
            return self.fetch(url)
        except RetryExhausted as e:
            self.log.warning("listing_fetch_failed", url=url, error=str(e))
            return ""

    def run(self) -> list[dict]:
        """Concurrent override — same shape as QuickcropScraper.run().

        Walks BC category sitemap, fans out all category-pages, then
        concurrently fetches every product page. See
        [[use-concurrent-fetches]] memory.
        """
        category_bases = bc_category_urls(_BASE, log=self.log)

        candidate_listing_urls: list[str] = []
        listing_meta: dict[str, tuple[str, str]] = {}
        for base_url in category_bases:
            category_name = _slug_to_label(base_url)
            for page in range(1, _MAX_PAGES_PER_CATEGORY + 1):
                url = base_url if page == 1 else f"{base_url}?page={page}"
                candidate_listing_urls.append(url)
                listing_meta[url] = (base_url, category_name)
        self.log.info(
            "listing_fan_out",
            categories=len(category_bases),
            urls=len(candidate_listing_urls),
        )
        listing_pages = fetch_all_concurrent(
            candidate_listing_urls,
            max_concurrent=_MAX_CONCURRENT,
            log=self.log,
        )

        product_url_to_listing: dict[str, tuple[str, str]] = {}
        listings_with_products = 0
        for listing_url, html in listing_pages.items():
            if not self._listing_has_grid(html):
                continue
            listings_with_products += 1
            _, category_name = listing_meta[listing_url]
            for product_url in self.parse_listing(html):
                product_url_to_listing.setdefault(
                    product_url, (listing_url, category_name)
                )
        self.log.info(
            "listings_resolved",
            listings_with_products=listings_with_products,
            unique_products=len(product_url_to_listing),
        )

        product_urls = list(product_url_to_listing)
        self.report.products_in = len(product_urls)
        product_pages = fetch_all_concurrent(
            product_urls,
            max_concurrent=_MAX_CONCURRENT,
            log=self.log,
        )

        results: list[dict] = []
        for product_url, html in product_pages.items():
            source_url, category = product_url_to_listing[product_url]
            try:
                record = self.parse_product(html, product_url, source_url, category)
            except Exception as e:  # noqa: BLE001
                self.log.warning("parse_product_failed", url=product_url, error=str(e))
                self._drop("parse_error")
                continue
            if record is None:
                self._drop("parse_returned_none")
                continue
            results.append(record)
            self.report.products_parsed += 1

        fetch_misses = len(product_urls) - len(product_pages)
        if fetch_misses:
            self.report.dropped["fetch_failed"] = fetch_misses

        self.log.info(
            "scrape_complete",
            source=self.source,
            in_=self.report.products_in,
            parsed=self.report.products_parsed,
            dropped=self.report.dropped,
            errors=self.report.error_count,
        )
        return results

    @staticmethod
    def _listing_has_grid(html: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        return bool(soup.select_one("ul.productGrid li.product a.card-wrapper"))

    def parse_listing(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[str] = []
        seen: set[str] = set()
        for a in soup.select("ul.productGrid li.product a.card-wrapper[href]"):
            href = _as_str(a.get("href"))
            if not href:
                continue
            url = re.sub(r"^https?://(?:www\.)?jparkers\.com", _BASE, href).split("?", 1)[0]
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        data = soup.select_one("section.productView-data")
        if data is None:
            return None

        product_name = _as_str(data.get("data-name")) or self._fallback_name(soup)
        if not product_name:
            return None

        price = _price_from_text(_as_str(data.get("data-price")) or "")
        if price is None:
            meta = soup.find("meta", attrs={"property": "product:price:amount"})
            if meta is not None:
                price = _price_from_text(_as_str(meta.get("content")) or "")

        img_url = self._extract_image(soup)
        description = self._extract_description(soup)
        size = self._extract_size(soup)

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": category,
            "product_name": product_name,
            "img_url": img_url,
            "description": description,
            "price": price,
            "size": size,
            "stock": None,
            "quantity": 1,
        }

    @staticmethod
    def _fallback_name(soup: BeautifulSoup) -> str | None:
        h1 = soup.select_one("h1.productView-title, h1")
        return h1.get_text(strip=True) if h1 else None

    @staticmethod
    def _extract_image(soup: BeautifulSoup) -> str | None:
        img = soup.select_one(".productView-img-container img, .productView-image img")
        if not img:
            return None
        return _as_str(img.get("src")) or _as_str(img.get("data-src"))

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str | None:
        # The PDP has no rich description; the accordion section under the
        # gallery carries the substantive content (Key Points / Plant Size /
        # Planting Notes / Soil Type). Use that as the description.
        sect = soup.select_one("section.productView-accordions")
        if sect is None:
            meta = soup.find("meta", attrs={"property": "og:description"})
            return _as_str(meta.get("content")) if meta else None
        text = sect.get_text(" ", strip=True)
        return text or None

    @staticmethod
    def _extract_size(soup: BeautifulSoup) -> str | None:
        # Listing cards expose "How Supplied:" lines (e.g. "Top-grade Tubers",
        # "Bare Root"). On the PDP this lives in the productView-options
        # block under a span.value if present.
        for label in soup.find_all(string=re.compile(r"How Supplied", re.IGNORECASE)):
            parent = label.find_parent()
            if not parent:
                continue
            # Look for sibling text after the label
            sib = parent.find_next_sibling()
            if sib:
                t = sib.get_text(" ", strip=True)
                if t:
                    return t
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, list) and v:
        first = v[0]
        return first if isinstance(first, str) else None
    return None


def _price_from_text(text: str) -> float | None:
    cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    parts = cleaned.rsplit(".", 1)
    if len(parts) == 2 and len(parts[1]) <= 2:
        cleaned = parts[0].replace(".", "") + "." + parts[1]
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _slug_to_label(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    return slug.replace("-", " ").title() if slug else ""


def get_product_data() -> list[dict]:
    with JParkersScraper() as scraper:
        return scraper.run()
