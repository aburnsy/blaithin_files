"""Gardens4You scraper — Cloudflare-fronted, needs Chrome TLS impersonation.

Coverage strategy: walk every product URL listed in the public sitemap
at ``/sitemaps/ie/sitemap.xml`` (6800+ products in one file).

Anti-bot strategy: G4Y is Cloudflare-fronted with active bot management.
httpx with a Chrome UA still gets 403s under any meaningful concurrency
because the TLS/JA3 fingerprint gives Python away. We use:

  - curl-cffi AsyncSession with ``impersonate="chrome"`` (real Chrome
    TLS + HTTP/2 + headers — defeats CF fingerprinting).
  - a homepage warmup to acquire the ``__cf_bm`` cookie before fan-out.
  - low concurrency (2) with per-request jitter (0.3-0.8s) — empirically
    CF tolerates this; conc=3 starts triggering blocks.
  - per-URL retry with exponential backoff on 403/429/503 — CF blocks
    are temporal and clear after a cooldown.
  - a consecutive-block circuit breaker that pauses the whole fleet
    once CF gets hostile, since digging the hole deeper just escalates.
"""

from __future__ import annotations

import asyncio
import random
import re

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from src.scrapers.base import BaseScraper

_BASE = "https://www.gardens4you.ie"
_HOME = f"{_BASE}/"
_SITEMAP = f"{_BASE}/sitemaps/ie/sitemap.xml"
_IMPERSONATE = "chrome"
_MAX_CONCURRENT = 2
# Adaptive jitter: start in SAFE, drop to FAST after N consecutive successes,
# snap back to SAFE on any CF block. The block rate observed at SAFE pace
# was ~21% with 0 full-exhaustions; FAST trades pacing for throughput when
# CF is calm and self-corrects within one block when it isn't.
_JITTER_SAFE = (0.3, 0.8)
_JITTER_FAST = (0.1, 0.3)
_FAST_MODE_THRESHOLD = 20
_REQUEST_TIMEOUT = 30.0
_MAX_ATTEMPTS = 4
_BLOCK_STATUSES = frozenset({403, 429, 503})
# Once this many *consecutive* product fetches hit a CF block, pause the
# whole session for a cooldown before resuming.
_CB_TRIP_COUNT = 5
_CB_PAUSE_SECONDS = 90.0


class _BlockedError(Exception):
    """All retry attempts for a single URL failed (CF block or network)."""

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
        """Fetch everything via curl-cffi (Chrome TLS impersonation), then parse.

        The fan-out is ~7000 product GETs; serial would take hours. But
        Cloudflare blocks above conc=2 even with TLS impersonation, so we
        pace deliberately — see module docstring."""
        fetched = asyncio.run(self._fetch_all())
        if fetched is None:
            return []
        sitemap_xml, pages = fetched

        product_urls = self.parse_listing(sitemap_xml)
        self.report.products_in = len(product_urls)
        self.log.info("sitemap_loaded", products=len(product_urls))

        results: list[dict] = []
        for url, html in pages.items():
            try:
                record = self.parse_product(html, url, _SITEMAP, "")
            except Exception as e:  # noqa: BLE001
                self.log.warning("parse_product_failed", url=url, error=str(e))
                self._drop("parse_error")
                continue
            if record is None:
                self._drop("parse_returned_none")
                continue
            results.append(record)
            self.report.products_parsed += 1

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

    async def _fetch_all(self) -> tuple[str, dict[str, str]] | None:
        """Drive the whole HTTP side: warmup → sitemap → paced product fan-out."""
        async with AsyncSession(impersonate=_IMPERSONATE, timeout=_REQUEST_TIMEOUT) as s:
            try:
                warm = await s.get(_HOME)
            except Exception as e:  # noqa: BLE001
                self.log.error("warmup_failed", error=str(e))
                self.report.error_count += 1
                return None
            self.log.info("warmup_done", status=warm.status_code)
            if warm.status_code in _BLOCK_STATUSES:
                self.log.error("warmup_blocked", status=warm.status_code)
                self.report.error_count += 1
                return None

            try:
                sitemap_xml = await self._fetch_with_retry(s, _SITEMAP)
            except _BlockedError as e:
                self.log.error("listing_fetch_failed", url=_SITEMAP, error=str(e))
                self.report.error_count += 1
                return None

            product_urls = self.parse_listing(sitemap_xml)

            sem = asyncio.Semaphore(_MAX_CONCURRENT)
            state = {"consecutive_blocks": 0, "consecutive_successes": 0, "fast_mode": False}
            cb_lock = asyncio.Lock()
            results: dict[str, str] = {}

            def on_block() -> None:
                state["consecutive_blocks"] += 1
                state["consecutive_successes"] = 0
                if state["fast_mode"]:
                    self.log.info("pacing_safe", reason="cf_block")
                    state["fast_mode"] = False

            async def fetch_one(url: str) -> None:
                async with sem:
                    # Circuit breaker: if CF is hot, pause everyone for a cooldown.
                    async with cb_lock:
                        if state["consecutive_blocks"] >= _CB_TRIP_COUNT:
                            self.log.warning(
                                "circuit_breaker_pause",
                                consecutive=state["consecutive_blocks"],
                                seconds=_CB_PAUSE_SECONDS,
                            )
                            await asyncio.sleep(_CB_PAUSE_SECONDS)
                            state["consecutive_blocks"] = 0
                    jitter_range = _JITTER_FAST if state["fast_mode"] else _JITTER_SAFE
                    await asyncio.sleep(random.uniform(*jitter_range))
                    try:
                        body = await self._fetch_with_retry(s, url, on_block=on_block)
                    except _BlockedError as e:
                        self.log.warning("product_fetch_failed", url=url, error=str(e))
                        return
                    results[url] = body
                    state["consecutive_blocks"] = 0
                    state["consecutive_successes"] += 1
                    if (
                        not state["fast_mode"]
                        and state["consecutive_successes"] >= _FAST_MODE_THRESHOLD
                    ):
                        self.log.info("pacing_fast", consecutive_successes=state["consecutive_successes"])
                        state["fast_mode"] = True

            await asyncio.gather(*(fetch_one(u) for u in product_urls))
            return sitemap_xml, results

    async def _fetch_with_retry(self, session: AsyncSession, url: str, on_block=None) -> str:
        """GET with exponential-backoff retry on CF blocks + network errors.

        Cookies persist on the session, so retries benefit from any
        ``__cf_bm`` / ``cf_clearance`` we've already acquired.

        ``on_block`` (callable, no args) is invoked once for every individual
        403/429/503 — not only on full exhaustion — so the caller's circuit
        breaker can react to a sustained CF block rate, not just total
        failures."""
        last: str = "no attempts"
        for attempt in range(_MAX_ATTEMPTS):
            self.log.info("fetch", url=url, attempt=attempt + 1)
            try:
                r = await session.get(url)
            except Exception as e:  # noqa: BLE001 — network/transport errors
                last = f"{type(e).__name__}: {e}"
                await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                continue
            if r.status_code == 200:
                return r.text
            last = f"HTTP {r.status_code}"
            self.log.warning("fetch_non_200", url=url, status=r.status_code, attempt=attempt + 1)
            if r.status_code in _BLOCK_STATUSES:
                if on_block is not None:
                    on_block()
                await asyncio.sleep(2 ** attempt + random.uniform(0, 1))
                continue
            # Non-retryable (404, 5xx other than 503, …) — give up immediately.
            break
        raise _BlockedError(f"{url}: {last} (after {_MAX_ATTEMPTS} attempts)")

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
