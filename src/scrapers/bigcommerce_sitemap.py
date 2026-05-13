"""Helper for discovering every category URL on a BigCommerce Stencil store.

BigCommerce exposes a sitemap index at ``/xmlsitemap.php`` with separate
sub-sitemaps per content type. The ``type=categories`` one lists every
category page across all pages. We walk the ``&page=N`` parameter until
no more URLs come back.

Used by the Mr Middleton and J Parker's scrapers — both BigCommerce
Stencil sites where full catalog coverage requires every category in
the navigation tree, not just a hand-picked subset.
"""

from __future__ import annotations

import re
import time

import httpx

_TIMEOUT = 30.0
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def bc_category_urls(base_url: str, *, log=None, throttle: float = 0.3) -> list[str]:
    """Return every category URL listed in ``<base_url>/xmlsitemap.php``.

    The sitemap is amortised across this scraper run — caller fetches
    once and pages through.
    """
    base = base_url.rstrip("/")
    with httpx.Client(
        headers={"User-Agent": _USER_AGENT},
        timeout=_TIMEOUT,
        follow_redirects=True,
    ) as client:
        index_xml = _fetch_text(client, f"{base}/xmlsitemap.php")
        sub_sitemaps = [
            u for u in _locs(index_xml) if "type=categories" in u
        ]
        urls: list[str] = []
        seen: set[str] = set()
        for sub in sub_sitemaps:
            # The index uses HTML-encoded ampersands; decode for httpx.
            sub_url = sub.replace("&amp;", "&")
            sub_xml = _fetch_text(client, sub_url)
            time.sleep(throttle)
            for loc in _locs(sub_xml):
                if loc not in seen:
                    seen.add(loc)
                    urls.append(loc)
    if log is not None:
        log.info("bc_categories_discovered", count=len(urls), site=base)
    return urls


def _fetch_text(client: httpx.Client, url: str) -> str:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.text


def _locs(xml: str) -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", xml)
