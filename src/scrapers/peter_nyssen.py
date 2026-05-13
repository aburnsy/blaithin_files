"""Peter Nyssen scraper — Cloudflare-fronted Magento 2 storefront.

Cloudflare's Managed Challenge fires on every plain GET, so we drive
``undetected_chromedriver`` (a patched Selenium Chrome that evades CF's
JS+webdriver fingerprinting). Non-headless mode is required — headless
still gets challenged. The CF interstitial typically clears in ~5-10s.

Coverage strategy: full catalog. After CF passes we pull the sitemap
in-browser, filter to every category page under ``/spring-planting/``
and ``/autumn-planting/`` (plus a handful of root-level category
endpoints), and walk each with ``?p=N`` pagination. Cross-category
duplicates are deduped by ``product_url``.

UK/NL bulb specialist — prices in GBP. Ships from NL to IE since
Brexit so ROI delivery is normal (~£17/€17 flat).
"""

from __future__ import annotations

import re
import time
from datetime import date

from bs4 import BeautifulSoup

from src.common.logging import get_logger
from src.common.report import ScrapeReport

_BASE = "https://www.peternyssen.com"
_SITEMAP = f"{_BASE}/sitemap.xml"
_CF_PASS_TIMEOUT = 30  # seconds to wait for Cloudflare challenge to clear
_PAGE_LOAD_WAIT = 1.5   # seconds after navigation before parsing

# The two product trees in the sitemap. Both top-level pages
# (/spring-planting.html, /autumn-planting.html) showed 0 products in
# probing, so we walk only the categories nested below them.
_PRODUCT_TREES = ("spring-planting", "autumn-planting")

# Root-level category pages (single segment .html) that carry products
# but live outside the seasonal trees.
_ROOT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("/accessories.html", "Accessories"),
    ("/gifts.html", "Gifts"),
)


class PeterNyssenScraper:
    """Browser-driven scraper. Not a BaseScraper subclass — the lifecycle
    (single shared Chrome session, CF-pass once, navigate-then-parse) is
    different enough that the BaseScraper.fetch() abstraction doesn't fit."""

    source = "peter_nyssen"

    def __init__(self) -> None:
        self.log = get_logger(f"scraper.{self.source}")
        self.report = ScrapeReport(source=self.source, run_date=date.today())
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

    def __exit__(self, *_args):
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

    def _fetch_sitemap(self) -> str:
        """Pull sitemap.xml via in-browser fetch (uses passed CF cookies)."""
        if self._driver is None:
            raise RuntimeError("Driver not initialised")
        return self._driver.execute_async_script(
            "const cb = arguments[arguments.length - 1];"
            f"fetch('{_SITEMAP}').then(r => r.text()).then(t => cb(t))"
            ".catch(e => cb('ERR: ' + e));"
        )

    def _category_seeds(self) -> list[tuple[str, str]]:
        """Every category-page URL we should walk, with a category label.

        Source: the sitemap. We include every .html URL nested under
        ``/spring-planting/`` or ``/autumn-planting/`` (any depth — leaf
        categories included, the deepest sub-categories add no extra
        products but cost nothing thanks to the URL-level dedupe).
        Single-segment root URLs are excluded — they're either landing
        pages with no products or product-detail pages.
        """
        sitemap = self._fetch_sitemap()
        urls = re.findall(r"<loc>([^<]+)</loc>", sitemap)
        seeds: list[tuple[str, str]] = []
        seen: set[str] = set()

        for url in urls:
            path = url.replace(_BASE, "", 1)
            if not path.endswith(".html"):
                continue
            segs = path.lstrip("/").rsplit(".", 1)[0].split("/")
            # Restrict to nested URLs under the two seasonal trees.
            if len(segs) < 2 or segs[0] not in _PRODUCT_TREES:
                continue
            category = _category_label(segs)
            if url not in seen:
                seen.add(url)
                seeds.append((url, category))

        for path, category in _ROOT_CATEGORIES:
            url = _BASE + path
            if url not in seen:
                seen.add(url)
                seeds.append((url, category))

        self.log.info("category_seeds", count=len(seeds))
        return seeds

    def run(self) -> list[dict]:
        if self._driver is None:
            raise RuntimeError("Scraper used outside of `with` block")

        results: list[dict] = []
        seen_product_urls: set[str] = set()

        seeds = self._category_seeds()
        for base_url, category in seeds:
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
                title = (self._driver.title or "").strip()

                # Skip 404 pages.
                if "Page Not Found" in title:
                    break

                cards = _extract_cards(html)
                if not cards:
                    # Parent landing pages with no products — skip silently.
                    break

                added_any = False
                for card in cards:
                    self.report.products_in += 1
                    record = self._record_from_card(
                        card, source_url=url, category=category
                    )
                    if record is None:
                        self.report.dropped["parse_returned_none"] = (
                            self.report.dropped.get("parse_returned_none", 0) + 1
                        )
                        continue
                    if record["product_url"] in seen_product_urls:
                        self.report.dropped["duplicate_across_categories"] = (
                            self.report.dropped.get("duplicate_across_categories", 0)
                            + 1
                        )
                        continue
                    seen_product_urls.add(record["product_url"])
                    results.append(record)
                    self.report.products_parsed += 1
                    added_any = True

                if not added_any:
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


def _category_label(segs: list[str]) -> str:
    """Best-effort human-readable label from the URL path segments.

    /spring-planting/dahlia-tubers.html         -> "Bulbs"
    /spring-planting/dahlia-tubers/decorative-dahlias.html -> "Bulbs"
    /autumn-planting/hardy-perennial-plants.html -> "Perennials"
    /accessories.html                            -> "Accessories"
    """
    if not segs:
        return ""
    top = segs[0]
    if top in ("spring-planting", "autumn-planting"):
        # "perennial-tulips" is still a tulip (bulb); only the actual
        # hardy-perennial-plants tree is the perennials category.
        if len(segs) >= 2 and segs[1] == "hardy-perennial-plants":
            return "Perennials"
        return "Bulbs"
    return top.replace("-", " ").title()


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
