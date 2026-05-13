"""Peter Nyssen scraper — Cloudflare-fronted Magento 2 storefront.

Cloudflare's Managed Challenge fires on every plain GET, so we drive
``undetected_chromedriver`` (a patched Selenium Chrome that evades CF's
JS+webdriver fingerprinting). Non-headless mode is required — headless
still gets challenged. The CF interstitial typically clears in ~5-10s.

Once past CF, the storefront is standard Magento: each listing page has
``article.product-item`` cards carrying name/price/url/image, and
``?p=N`` paginates. Per-product fetches aren't needed for the matching
pipeline, so we parse cards directly.

UK/NL bulb specialist — prices in GBP. Ships from NL to IE since Brexit
so ROI delivery is normal (~£17/€17 flat).
"""

from __future__ import annotations

import importlib
import re
import time
from datetime import date

from bs4 import BeautifulSoup

from src.common.logging import get_logger
from src.common.report import ScrapeReport

_BASE = "https://www.peternyssen.com"
_CF_PASS_TIMEOUT = 30  # seconds to wait for Cloudflare challenge to clear
_PAGE_LOAD_WAIT = 2.0   # seconds after navigation before parsing


class PeterNyssenScraper:
    """Browser-driven scraper. Not a BaseScraper subclass — the lifecycle
    (single shared Chrome session, CF-pass once, navigate-then-parse) is
    different enough that the BaseScraper.fetch() abstraction doesn't fit."""

    source = "peter_nyssen"

    def __init__(self, config_module: str = "config.peter_nyssen") -> None:
        self.log = get_logger(f"scraper.{self.source}")
        self.report = ScrapeReport(source=self.source, run_date=date.today())
        self._config = importlib.import_module(config_module)
        self._driver = None

    def __enter__(self):
        # Imported lazily so the rest of the codebase (and CI lint) doesn't
        # require Selenium/UC just to import this module.
        import undetected_chromedriver as uc  # noqa: PLC0415

        opts = uc.ChromeOptions()
        opts.add_argument("--window-size=1400,900")
        # Headless still gets challenged by CF — must be non-headless.
        self._driver = uc.Chrome(options=opts, version_main=None, headless=False)
        self._driver.set_page_load_timeout(60)
        self._pass_cf()
        return self

    def __exit__(self, *args):
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:  # noqa: BLE001 — uc's __del__ races on Windows
                pass
            self._driver = None

    def _pass_cf(self) -> None:
        if self._driver is None:
            raise RuntimeError("Driver not initialised")
        self._driver.get(_BASE + "/")
        for i in range(_CF_PASS_TIMEOUT):
            time.sleep(1)
            if "Just a moment" not in (self._driver.title or ""):
                self.log.info("cf_passed", seconds=i + 1)
                return
        raise RuntimeError(
            f"Cloudflare challenge did not clear within {_CF_PASS_TIMEOUT}s — "
            "site likely tightened its rules; bypass library may need an update."
        )

    def run(self) -> list[dict]:
        if self._driver is None:
            raise RuntimeError("Scraper used outside of `with` block")

        results: list[dict] = []
        seen_urls: set[str] = set()

        for base_url, category in self._config.data_sources:
            page = 1
            while True:
                url = base_url if page == 1 else f"{base_url}?p={page}"
                try:
                    self._driver.get(url)
                except Exception as e:  # noqa: BLE001
                    self.log.warning("nav_failed", url=url, error=str(e))
                    self.report.error_count += 1
                    break

                time.sleep(_PAGE_LOAD_WAIT)
                html = self._driver.page_source

                cards = _extract_cards(html)
                if not cards:
                    break

                added_any = False
                for card in cards:
                    self.report.products_in += 1
                    record = self._record_from_card(card, source_url=url, category=category)
                    if record is None:
                        self.report.dropped["parse_returned_none"] = (
                            self.report.dropped.get("parse_returned_none", 0) + 1
                        )
                        continue
                    if record["product_url"] in seen_urls:
                        self.report.dropped["duplicate_across_categories"] = (
                            self.report.dropped.get("duplicate_across_categories", 0) + 1
                        )
                        continue
                    seen_urls.add(record["product_url"])
                    results.append(record)
                    self.report.products_parsed += 1
                    added_any = True

                if not added_any:
                    # Pagination wrapped or all cards were duplicates — stop.
                    break

                if not _has_next_page(html):
                    break
                page += 1

        self.log.info(
            "scrape_complete",
            source=self.source,
            in_=self.report.products_in,
            parsed=self.report.products_parsed,
            dropped=self.report.dropped,
            errors=self.report.error_count,
        )
        return results

    def _record_from_card(
        self, card: dict, *, source_url: str, category: str
    ) -> dict | None:
        if not card.get("product_name") or not card.get("product_url"):
            return None
        return {
            "source": self.source,
            "source_url": source_url,
            "product_url": card["product_url"],
            "category": category,
            "product_name": card["product_name"],
            "img_url": card.get("img_url"),
            "description": None,
            "price": card.get("price"),
            "size": None,
            "stock": None,
            "quantity": 1,
        }


# ---------------------------------------------------------------------------
# HTML extraction helpers (module-level so tests can call them directly)
# ---------------------------------------------------------------------------


def _extract_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for el in soup.select("form.product-item, li.product-item, .product-item-info"):
        link = el.select_one("a.product-item-photo, a.product-item-link")
        if link is None:
            continue
        href = link.get("href")
        if not isinstance(href, str):
            continue
        name_el = el.select_one(".product-item-link") or link
        name = name_el.get_text(strip=True)
        if not name:
            # fall back to image alt or aria-label
            img = el.select_one("img")
            if img is not None:
                alt = img.get("alt")
                if isinstance(alt, str):
                    name = alt.strip()
        if not name:
            continue
        price = _extract_price(el)
        img_url = _extract_image(el)
        out.append(
            {
                "product_name": name,
                "product_url": href.split("?", 1)[0],
                "img_url": img_url,
                "price": price,
            }
        )
    return out


def _extract_price(card) -> float | None:
    # Prefer the sale price when present; fall back to the regular price.
    # Skip the strikethrough .old-price.
    price_el = card.select_one(".special-price .price, .normal-price .price")
    if price_el is None:
        # First non-old-price span.price in the card.
        for span in card.select("span.price"):
            parents = " ".join(_class_chain(span))
            if "old-price" in parents:
                continue
            price_el = span
            break
    if price_el is None:
        return None
    return _price_from_text(price_el.get_text(strip=True))


def _class_chain(el) -> list[str]:
    out: list[str] = []
    cur = el
    while cur is not None and hasattr(cur, "get"):
        cls = cur.get("class")
        if isinstance(cls, list):
            out.extend(cls)
        cur = cur.parent
    return out


def _extract_image(card) -> str | None:
    for img in card.select("img"):
        src = img.get("src") or img.get("data-src")
        if not isinstance(src, str):
            continue
        # Skip the sale-overlay badges that live in /media/amasty/amlabel/.
        if "/amlabel/" in src:
            continue
        return src
    return None


def _has_next_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select_one("li.pages-item-next a, li.item.pages-item-next"))


def _price_from_text(text: str) -> float | None:
    cleaned = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    parts = cleaned.rsplit(".", 1)
    if len(parts) == 2 and len(parts[1]) <= 2:
        cleaned = parts[0].replace(".", "") + "." + parts[1]
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def get_product_data() -> list[dict]:
    with PeterNyssenScraper() as scraper:
        return scraper.run()
