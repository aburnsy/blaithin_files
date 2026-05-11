"""Retry-aware HTTP client wrapping httpx + tenacity."""

from __future__ import annotations

import time

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.common.logging import get_logger

log = get_logger("scrapers.http")

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; blaithin-bot/1.0; +https://github.com/aburnsy/blaithin_files)"
)


class RetryExhausted(Exception):
    """All retry attempts failed."""


def build_client(
    *,
    rate_limit_seconds: float = 1.0,
    user_agent: str | None = None,
    timeout: float = 30.0,
) -> httpx.Client:
    """Build an httpx.Client with sensible defaults.

    Caller is responsible for closing the client (use as context manager:
    `with build_client() as c: ...`).
    """
    return httpx.Client(
        headers={"User-Agent": user_agent or _DEFAULT_USER_AGENT},
        timeout=timeout,
        follow_redirects=True,
    )


def fetch_html(
    client: httpx.Client,
    url: str,
    *,
    max_attempts: int = 3,
    rate_limit_seconds: float = 1.0,
) -> str:
    """GET the URL, retrying on 5xx/429/timeouts. Returns response text."""
    if rate_limit_seconds > 0:
        time.sleep(rate_limit_seconds)

    try:
        for attempt in Retrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError)),
            reraise=True,
        ):
            with attempt:
                log.info("fetch", url=url, attempt=attempt.retry_state.attempt_number)
                response = client.get(url)
                response.raise_for_status()
                return response.text
    except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError) as e:
        raise RetryExhausted(f"{url}: {e}") from e
    raise RetryExhausted(f"{url}: unknown")  # unreachable
