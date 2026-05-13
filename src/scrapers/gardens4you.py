"""Gardens4You scraper — Magento-style site, no JS rendering needed.

Coverage strategy: walk every product URL listed in the public sitemap
at ``/sitemaps/ie/sitemap.xml`` (6800+ products in one file). Previously
the scraper used a hand-picked 9-category seed list and missed most of
the catalog — see [[full-coverage]] memory.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper
from src.scrapers.concurrent import fetch_all_concurrent

_BASE = "https://www.gardens4you.ie"
_SITEMAP = f"{_BASE}/sitemaps/ie/sitemap.xml"
# G4Y is Cloudflare-fronted and now 403s the default bot UA on product pages
# (sitemap still served). Use a Chrome UA — same convention as ardcarne.
_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_MAX_CONCURRENT = 3

_size_pattern_cm = re.compile(r"\d+\s*cm", re.IGNORECASE)
_size_pattern_litre = re.compile(r"\d+\s*ltr", re.IGNORECASE)
_size_pattern_pval = re.compile(r"P\s*\d+")
_stock_pattern = re.compile(r"\d+")


class Gardens4YouScraper(BaseScraper):
    source = "gardens4you"
    rate_limit_seconds = 0.0  # serial path unused — we fetch concurrently

    def discover_categories(self) -> list[tuple[str, str]]:
        """Single seed: the sitemap. ``parse_listing`` then pulls every
        product URL from the returned XML."""
        return [(_SITEMAP, "")]

    def parse_listing(self, html: str) -> list[str]:
        """Extract every product URL from the sitemap XML."""
        urls = re.findall(r"<loc>([^<]+)</loc>", html)
        out: list[str] = []
        seen: set[str] = set()
        for u in urls:
            if not u.endswith(".html"):
                continue
            url = u.split("?", 1)[0]
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def run(self) -> list[dict]:
        """Concurrent override: sitemap fan-out is ~7000 product GETs, way
        too slow serially. See [[use-concurrent-fetches]] memory."""
        from src.scrapers.http import RetryExhausted  # noqa: PLC0415

        sitemap_url = _SITEMAP
        try:
            sitemap_xml = self.fetch(sitemap_url)
        except RetryExhausted as e:
            self.log.error("listing_fetch_failed", url=sitemap_url, error=str(e))
            self.report.error_count += 1
            return []

        product_urls = self.parse_listing(sitemap_xml)
        self.report.products_in = len(product_urls)
        self.log.info("sitemap_loaded", products=len(product_urls))

        pages = fetch_all_concurrent(
            product_urls,
            max_concurrent=_MAX_CONCURRENT,
            user_agent=_CHROME_UA,
            log=self.log,
        )

        results: list[dict] = []
        for url, html in pages.items():
            try:
                record = self.parse_product(html, url, sitemap_url, "")
            except Exception as e:  # noqa: BLE001
                self.log.warning("parse_product_failed", url=url, error=str(e))
                self._drop("parse_error")
                continue
            if record is None:
                self._drop("parse_returned_none")
                continue
            results.append(record)
            self.report.products_parsed += 1

        # URLs that didn't fetch successfully
        missing = len(product_urls) - len(pages)
        if missing:
            self.report.dropped["fetch_failed"] = missing

        self.log.info(
            "scrape_complete",
            source=self.source,
            in_=self.report.products_in,
            parsed=self.report.products_parsed,
            dropped=self.report.dropped,
            errors=self.report.error_count,
        )
        return results

    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | None:
        """Parse a product page. Returns a dict or None to drop (never raises)."""
        soup = BeautifulSoup(html, "html.parser")

        # Product name — required; if missing this is not a real product page
        name_el = soup.find("h1")
        if not name_el:
            return None
        product_name = name_el.get_text(strip=True)
        if not product_name:
            return None

        # Price — prefer data-price-amount attribute (exact float), fall back to span text
        price = self._extract_price(soup)

        # Size — nullable; try product attributes first, then name; no fake fallbacks
        size = self._extract_size(soup, product_name)

        # Stock — best-effort integer; None if not found
        stock = self._extract_stock(soup)

        # Image
        img_el = soup.find("img", class_=re.compile(r"product"))
        img_url = img_el.get("src") if img_el else None

        # Description
        desc_el = soup.find("div", class_="product attribute description")
        description = desc_el.get_text(strip=True) if desc_el else None

        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": product_url,
            "category": category,
            "product_name_raw": product_name,
            "img_url": img_url,
            "description": description,
            "price_native": price,
            "currency": "EUR",
            "size": size,
            "stock": stock,
        }

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_price(soup: BeautifulSoup) -> float | None:
        # Most reliable: data-price-amount attribute on the main product price widget
        el = soup.find(attrs={"data-price-amount": True})
        if el:
            try:
                return float(el["data-price-amount"])
            except (ValueError, TypeError):
                pass
        # Fallback: first span.price
        price_span = soup.select_one("span.price")
        if price_span:
            text = price_span.get_text(strip=True)
            m = re.search(r"(\d+[.,]\d+|\d+)", text.replace(",", "."))
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    @staticmethod
    def _extract_size(soup: BeautifulSoup, product_name: str) -> str | None:
        """Extract pot/height size from product attribute divs or product name.

        Returns None if no size signal found — caller must treat size as optional.
        Previously the legacy code raised Exception or returned 'Bare Root' as a
        silent fallback; both behaviours are removed.
        """
        # Check Magento product attribute divs first (most reliable)
        for div in soup.find_all("div", class_=re.compile(r"product attribute")):
            text = div.get_text(strip=True)
            # "Nursery pot size 9cm" / "Delivered as bare root" etc.
            if "pot size" in text.lower() or "nursery" in text.lower():
                m = re.search(_size_pattern_cm, text)
                if m:
                    return m.group(0)
            if "root" in text.lower() or "bare" in text.lower():
                return "Bare Root"
            if "seed" in text.lower():
                return "Seeds"
            # Generic cm match in an attribute div
            m = re.search(_size_pattern_cm, text)
            if m:
                return m.group(0)

        # Fall back to product name
        if m := re.search(_size_pattern_cm, product_name):
            return m.group(0)
        if m := re.search(_size_pattern_litre, product_name):
            return m.group(0).replace("tr", "")
        if m := re.search(_size_pattern_pval, product_name):
            return m.group(0)
        if "bare root" in product_name.lower():
            return "Bare Root"

        return None  # Unknown — let caller handle as nullable

    @staticmethod
    def _extract_stock(soup: BeautifulSoup) -> int | None:
        """Return stock count or None."""
        stock_span = soup.find("span", class_=re.compile(r"amstockstatus"))
        if stock_span:
            text = stock_span.get_text(strip=True)
            # "Stock 100+" -> 100  |  "Out of stock" -> 0
            if "out of stock" in text.lower():
                return 0
            m = re.search(_stock_pattern, text)
            if m:
                return int(m.group(0))
        return None


# ---------------------------------------------------------------------------
# Backward-compat shim — load_bronze_data.py calls get_product_data()
# ---------------------------------------------------------------------------

def get_product_data() -> list[dict]:
    with Gardens4YouScraper() as scraper:
        return scraper.run()
