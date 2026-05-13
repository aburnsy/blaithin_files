"""BaseScraper ABC + lifecycle helpers.

Each site-specific scraper subclasses BaseScraper and implements three hooks:
  - discover_categories() -> list of (url, category_name) pairs
  - parse_listing(html) -> list of product URLs
  - parse_product(html, product_url, source_url, category) -> dict | None

The base class handles HTTP + retries + report tracking + lifecycle. Subclasses
that need JS rendering can override fetch() to spin up Playwright.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from src.common.logging import get_logger
from src.common.report import ScrapeReport
from src.scrapers.http import RetryExhausted, build_client, fetch_html


class BaseScraper(ABC):
    """Base class for all nursery scrapers."""

    source: str  # subclasses MUST override (e.g. "tullys")
    rate_limit_seconds: float = 1.0
    max_attempts: int = 3

    def __init__(self) -> None:
        if not getattr(self, "source", None):
            raise TypeError(f"{type(self).__name__} must define `source` class attribute")
        self.log = get_logger(f"scraper.{self.source}")
        self.report = ScrapeReport(source=self.source, run_date=date.today())
        self._client = None

    def __enter__(self):
        self._client = build_client(rate_limit_seconds=self.rate_limit_seconds)
        return self

    def __exit__(self, *args):
        if self._client is not None:
            self._client.close()
            self._client = None

    @abstractmethod
    def discover_categories(self) -> list[tuple[str, str]]:
        """Return [(category_url, category_name), ...] to scrape."""

    @abstractmethod
    def parse_listing(self, html: str) -> list[str]:
        """Given category page HTML, return list of product URLs."""

    @abstractmethod
    def parse_product(
        self, html: str, product_url: str, source_url: str, category: str
    ) -> dict | list[dict] | None:
        """Given product page HTML, return a row, a list of rows (one per
        variant), or None to drop. List return supports WooCommerce-style
        variable products where each size emits its own row."""

    def fetch(self, url: str) -> str:
        """Default fetch: HTTP via httpx + tenacity. Override for JS rendering."""
        if self._client is None:
            raise RuntimeError("Scraper used outside of `with` block")
        return fetch_html(
            self._client,
            url,
            max_attempts=self.max_attempts,
            rate_limit_seconds=self.rate_limit_seconds,
        )

    def run(self) -> list[dict]:
        """Run the full scrape. Returns list of product dicts."""
        results: list[dict] = []
        seen_product_urls: set[str] = set()
        for category_url, category_name in self.discover_categories():
            try:
                listing_html = self.fetch(category_url)
            except RetryExhausted as e:
                self.log.error("listing_fetch_failed", url=category_url, error=str(e))
                self.report.error_count += 1
                continue

            for product_url in self.parse_listing(listing_html):
                if product_url in seen_product_urls:
                    continue
                seen_product_urls.add(product_url)
                self.report.products_in += 1
                try:
                    product_html = self.fetch(product_url)
                except RetryExhausted as e:
                    self.log.warning("product_fetch_failed", url=product_url, error=str(e))
                    self._drop("fetch_failed")
                    continue

                try:
                    record = self.parse_product(
                        product_html, product_url, category_url, category_name
                    )
                except Exception as e:  # noqa: BLE001 — catch-all is intentional here
                    self.log.warning("parse_product_failed", url=product_url, error=str(e))
                    self._drop("parse_error")
                    continue

                if record is None:
                    self._drop("parse_returned_none")
                    continue

                rows = record if isinstance(record, list) else [record]
                if not rows:
                    self._drop("parse_returned_empty")
                    continue
                results.extend(rows)
                self.report.products_parsed += len(rows)

        self.log.info(
            "scrape_complete",
            source=self.source,
            in_=self.report.products_in,
            parsed=self.report.products_parsed,
            dropped=self.report.dropped,
            errors=self.report.error_count,
        )
        return results

    def _drop(self, reason: str) -> None:
        self.report.dropped[reason] = self.report.dropped.get(reason, 0) + 1
