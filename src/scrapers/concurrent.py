"""Concurrent HTTP helper for scrapers that need to fan out N GET requests.

The default ``BaseScraper.fetch`` is synchronous + rate-limited and is fine
for scrapers that hit a paginated API (Shopify ``/products.json``, WooCommerce
Store API, Magento GraphQL) where one request returns many products. For
scrapers that need ONE GET per product — sitemap-driven Ardcarne/Gardens4You/
Peter Nyssen, or BC-stencil QuickCrop/Mr Middleton/J Parker's — serial fetches
take hours. This module runs the same GETs concurrently via ``httpx.AsyncClient``.

Typical use::

    pages = fetch_all_concurrent(urls, max_concurrent=10, log=self.log)
    for url, html in pages.items():
        record = self.parse_product(html, url, ...)

The function returns a dict keyed by URL → response body. Failed/timed-out
requests are reported via the log and dropped from the result.
"""

from __future__ import annotations

import asyncio
from typing import Iterable

import httpx

# Match the serial path's UA so a scraper that worked one-at-a-time keeps
# working in concurrent mode. Sites that need a real-browser UA (Ardcarne,
# Peter Nyssen) pass their own.
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; blaithin-bot/1.0; +https://github.com/aburnsy/blaithin_files)"
)


def fetch_all_concurrent(
    urls: Iterable[str],
    *,
    max_concurrent: int = 10,
    timeout: float = 30.0,
    user_agent: str | None = None,
    log=None,
) -> dict[str, str]:
    """Fetch every URL concurrently. Returns ``{url: response_text}``.

    URLs that fail (network error, 5xx, timeout) are logged at warning level
    and omitted from the result. Order of results is not guaranteed to match
    input order.

    Parameters
    ----------
    urls
        Distinct URLs to fetch. The function deduplicates internally.
    max_concurrent
        Cap on simultaneous in-flight requests. ~10 is a polite default;
        push higher only for sites you know can take it.
    timeout
        Per-request timeout in seconds.
    user_agent
        Override the default Chrome-style UA. Some sites (Ardcarne) reject
        the bot UA; sites that don't (most Shopify/Woo APIs) don't care.
    log
        Optional structlog-style logger to record successes/failures.
    """
    unique = list(dict.fromkeys(urls))
    if not unique:
        return {}
    return asyncio.run(
        _fetch_all(
            unique,
            max_concurrent=max_concurrent,
            timeout=timeout,
            user_agent=user_agent or _DEFAULT_USER_AGENT,
            log=log,
        )
    )


async def _fetch_all(
    urls: list[str],
    *,
    max_concurrent: int,
    timeout: float,
    user_agent: str,
    log,
) -> dict[str, str]:
    sem = asyncio.Semaphore(max_concurrent)
    limits = httpx.Limits(
        max_connections=max_concurrent, max_keepalive_connections=max_concurrent
    )
    async with httpx.AsyncClient(
        headers={"User-Agent": user_agent},
        timeout=timeout,
        follow_redirects=True,
        limits=limits,
        http2=False,
    ) as client:

        async def fetch_one(url: str) -> tuple[str, str | None]:
            async with sem:
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return url, resp.text
                except Exception as e:  # noqa: BLE001 — log every failure
                    if log is not None:
                        log.warning("concurrent_fetch_failed", url=url, error=str(e))
                    return url, None

        results = await asyncio.gather(*(fetch_one(u) for u in urls))

    out: dict[str, str] = {}
    successes = 0
    for url, body in results:
        if body is not None:
            out[url] = body
            successes += 1
    if log is not None:
        log.info(
            "concurrent_fetch_done",
            requested=len(urls),
            succeeded=successes,
            failed=len(urls) - successes,
        )
    return out
