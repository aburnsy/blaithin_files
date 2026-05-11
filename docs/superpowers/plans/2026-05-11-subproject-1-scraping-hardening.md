# Sub-project 1: Scraping Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the per-site one-off scraper pattern with a shared `BaseScraper` foundation (tenacity retries, structlog logging, pydantic validation, context-managed lifecycle, per-run report). Rewrite gardens4you as the reference exemplar. Add 2 high-value new nursery scrapers from the research (Hedging.ie, David Austin EU). Fix cross-platform path bugs.

**Scope cap:** Sub-project 1 lands the foundation and proves the pattern. Rewriting the other 4 existing scrapers (arboretum, carragh, quickcrop, tullys, rhs) and adding more nurseries from research are tracked as incremental follow-ups — not part of this plan.

**Architecture:** Compose, don't inherit. `BaseScraper` is a small abstract class with `fetch()`, `parse_listing()`, `parse_product()` hooks; the heavy lifting (retries, logging, validation, lifecycle) lives in standalone helpers each scraper can use directly. Pydantic `ProductRecord` (from sub-project 2) is the contract.

**Tech Stack:** Python 3.11+, httpx, tenacity, structlog, pydantic v2 (already in), pytest-recording (vcrpy), playwright (lazy import — only loaded when a scraper needs JS rendering).

**Spec reference:** `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` §7.

---

## Phases

| Phase | Tasks | Output |
|---|---|---|
| **A. Foundation** | 1–6 | BaseScraper, http client w/ retries, structlog config, pydantic ProductRecord scraper-side, ScrapeReport, snapshot-diff helper |
| **B. Cross-platform paths** | 7 | storage.py uses pathlib; works on Linux CI |
| **C. Reference rewrite** | 8 | gardens4you ported to BaseScraper; pre-existing `raise Exception` removed |
| **D. New nursery scrapers** | 9–10 | Hedging.ie (free delivery — top value pick) + David Austin EU (must use eu.davidaustinroses.com per research) |
| **E. VCR fixtures + smoke** | 11–12 | One real-page fixture per scraper; smoke tests in CI-friendly form |

Total: ~12 tasks, ~3-5 days.

---

## File structure

**Created:**

| Path | Responsibility |
|---|---|
| `src/scrapers/base.py` | `BaseScraper` ABC, helpers `fetch_html`, `fetch_json`, `WithRetry`, `with_driver` context manager |
| `src/scrapers/http.py` | `httpx` client factory with `tenacity` retry on 429/5xx/timeouts; per-site rate limit |
| `src/common/logging.py` | structlog config — JSON to `logs/{date}.jsonl`, pretty to stdout |
| `src/common/report.py` | `ScrapeReport` dataclass + `snapshot_diff(report, history) -> alerts: list[str]` |
| `src/scrapers/hedgingie.py` | New scraper |
| `src/scrapers/david_austin.py` | New scraper |
| `tests/scrapers/test_base.py` | Tests for base helpers (retries, lifecycle, report) |
| `tests/scrapers/test_gardens4you_rewrite.py` | VCR-backed regression tests |
| `tests/scrapers/test_hedgingie.py` | VCR-backed |
| `tests/scrapers/test_david_austin.py` | VCR-backed |
| `tests/fixtures/cassettes/` | VCR cassette directory (committed) |

**Modified:**

| Path | Change |
|---|---|
| `requirements.txt` | + `tenacity`, `structlog`, `httpx`, `pytest-recording` (Playwright deferred to scrapers that need it) |
| `src/scrapers/gardens4you.py` | Rewritten on `BaseScraper` |
| `src/common/storage.py` | `pathlib.Path` instead of `data\\{source}\\…` Windows-only literals |
| `load_bronze_data.py` | Add `farmer_gracy`, `bulbi`, `greengardenflowerbulbs`, `hedgingie`, `david_austin` to `--site` choices and the match/case |
| `config/nurseries.yaml` | Add `hedgingie` and `david_austin` entries |

**Untouched in this sub-project (incremental follow-ups):**

- arboretum, carragh, quickcrop, tullys, rhs scraper bodies (kept as-is until each is touched in a follow-up)
- 8 other nurseries from research (Future Forests, Newlands, Mr Middleton, Brown Envelope, Caragh extras, etc.) — same pattern, follow-ups
- requests-html removal (forced by individual scraper rewrites)

---

## Phase A — Foundation

### Task 1: Add deps + structlog config

**Files:**
- Modify: `requirements.txt`
- Create: `src/common/logging.py`
- Create: `tests/common/test_logging.py`

- [ ] **Step 1: Add deps**

Append to `requirements.txt`:
```
tenacity
structlog
pytest-recording
```
Then `pip install -r requirements.txt`.

- [ ] **Step 2: Failing test**

Create `tests/common/test_logging.py`:
```python
"""Tests for structlog configuration."""

import json
from pathlib import Path

import pytest


def test_get_logger_returns_bound_logger():
    from src.common.logging import get_logger
    log = get_logger("test")
    assert log is not None


def test_logs_are_json_to_file(tmp_path, monkeypatch):
    from src.common import logging as logging_mod

    log_file = tmp_path / "test.jsonl"
    monkeypatch.setattr(logging_mod, "LOG_FILE", log_file)
    logging_mod.configure(force=True)

    log = logging_mod.get_logger("test_emit")
    log.info("hello", value=42, source="tullys")

    # Flush handlers
    import logging as stdlib_logging
    for h in stdlib_logging.getLogger().handlers:
        h.flush()

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) >= 1
    record = json.loads(lines[-1])
    assert record["event"] == "hello"
    assert record["value"] == 42
    assert record["source"] == "tullys"
```

- [ ] **Step 3: Implement `src/common/logging.py`**

```python
"""Structured logging configuration.

JSON to `logs/<date>.jsonl` (machine-readable) + pretty to stdout (human).
Call `configure()` once at the start of any entry point that should log.
"""

from __future__ import annotations

import logging as stdlib_logging
import sys
from datetime import date
from pathlib import Path

import structlog

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE: Path | None = None  # set by configure() based on date


def configure(*, force: bool = False) -> None:
    """Initialise structlog + stdlib logging. Idempotent unless force=True."""
    global LOG_FILE

    if LOG_FILE is not None and not force:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / f"{date.today().isoformat()}.jsonl"

    file_handler = stdlib_logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(stdlib_logging.INFO)
    file_handler.setFormatter(stdlib_logging.Formatter("%(message)s"))

    stream_handler = stdlib_logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stdlib_logging.INFO)

    root = stdlib_logging.getLogger()
    root.handlers = [file_handler, stream_handler]
    root.setLevel(stdlib_logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(stdlib_logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a bound logger; auto-configures on first call."""
    if LOG_FILE is None:
        configure()
    return structlog.get_logger(name)
```

- [ ] **Step 4: Run tests + commit**

```
pytest tests/common/test_logging.py -v
```
Expect: 2 passed.

```bash
git add requirements.txt src/common/logging.py tests/common/test_logging.py
git commit -m "$(cat <<'EOF'
add structlog config: JSON to logs/<date>.jsonl + pretty to stdout

Foundation for sub-project 1. Single configure() call wires both
file + stream handlers; get_logger() auto-configures on first use.
Idempotent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: HTTP client with tenacity retries

**Files:**
- Create: `src/scrapers/http.py`
- Create: `tests/scrapers/test_http.py`

- [ ] **Step 1: Failing test**

Create `tests/scrapers/test_http.py`:
```python
"""Tests for the retry-aware HTTP client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.scrapers.http import build_client, fetch_html, RetryExhausted


def test_build_client_returns_httpx_client():
    client = build_client(rate_limit_seconds=0)
    assert isinstance(client, httpx.Client)
    client.close()


@patch("src.scrapers.http.httpx.Client.get")
def test_fetch_html_succeeds_first_try(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text="<html>ok</html>", raise_for_status=lambda: None)
    client = build_client(rate_limit_seconds=0)
    html = fetch_html(client, "https://example.com")
    assert html == "<html>ok</html>"
    client.close()


@patch("src.scrapers.http.httpx.Client.get")
def test_fetch_html_retries_on_500(mock_get):
    # 500, 500, 200 — should succeed on third attempt
    err_resp = MagicMock(status_code=500)
    err_resp.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=err_resp)
    ok_resp = MagicMock(status_code=200, text="<html>ok</html>", raise_for_status=lambda: None)
    mock_get.side_effect = [err_resp, err_resp, ok_resp]

    client = build_client(rate_limit_seconds=0)
    html = fetch_html(client, "https://example.com", max_attempts=3)
    assert html == "<html>ok</html>"
    assert mock_get.call_count == 3
    client.close()


@patch("src.scrapers.http.httpx.Client.get")
def test_fetch_html_gives_up_after_max(mock_get):
    err_resp = MagicMock(status_code=503)
    err_resp.raise_for_status.side_effect = httpx.HTTPStatusError("503", request=MagicMock(), response=err_resp)
    mock_get.return_value = err_resp

    client = build_client(rate_limit_seconds=0)
    with pytest.raises(RetryExhausted):
        fetch_html(client, "https://example.com", max_attempts=2)
    client.close()
```

- [ ] **Step 2: Implement `src/scrapers/http.py`**

```python
"""Retry-aware HTTP client wrapping httpx + tenacity."""

from __future__ import annotations

import time
from typing import Optional

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
    user_agent: Optional[str] = None,
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
```

- [ ] **Step 3: Run tests + commit**

```
pytest tests/scrapers/test_http.py -v
```
Expect: 4 passed.

```bash
git add src/scrapers/http.py tests/scrapers/test_http.py
git commit -m "$(cat <<'EOF'
add retry-aware http client (httpx + tenacity)

Replaces requests-html for non-JS scrapes. Exponential backoff on
5xx/429/timeouts; 3 attempts by default. RetryExhausted on final
failure. Per-site rate limit defaults to 1s.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: ScrapeReport + snapshot diff

**Files:**
- Create: `src/common/report.py`
- Create: `tests/common/test_report.py`

- [ ] **Step 1: Failing test**

Create `tests/common/test_report.py`:
```python
"""Tests for scrape report and snapshot diff."""

from datetime import date

from src.common.report import ScrapeReport, snapshot_diff


def test_report_init():
    r = ScrapeReport(source="tullys", run_date=date(2026, 5, 11))
    assert r.source == "tullys"
    assert r.products_in == 0
    assert r.products_parsed == 0
    assert r.dropped == {}


def test_report_increment():
    r = ScrapeReport(source="tullys", run_date=date(2026, 5, 11))
    r.products_in += 100
    r.products_parsed += 95
    r.dropped["missing_price"] = 3
    r.dropped["parse_error"] = 2
    assert r.products_parsed == 95
    assert sum(r.dropped.values()) == 5


def test_snapshot_diff_no_history():
    today = ScrapeReport(source="tullys", run_date=date(2026, 5, 11), products_parsed=100)
    alerts = snapshot_diff(today, history=[])
    assert alerts == []


def test_snapshot_diff_within_threshold():
    today = ScrapeReport(source="tullys", run_date=date(2026, 5, 11), products_parsed=110)
    history = [
        ScrapeReport(source="tullys", run_date=date(2026, 5, 4 + i), products_parsed=100)
        for i in range(7)
    ]
    alerts = snapshot_diff(today, history, threshold=0.25)
    assert alerts == []


def test_snapshot_diff_exceeds_threshold():
    today = ScrapeReport(source="tullys", run_date=date(2026, 5, 11), products_parsed=50)  # 50% drop
    history = [
        ScrapeReport(source="tullys", run_date=date(2026, 5, 4 + i), products_parsed=100)
        for i in range(7)
    ]
    alerts = snapshot_diff(today, history, threshold=0.25)
    assert len(alerts) == 1
    assert "tullys" in alerts[0]
    assert "50%" in alerts[0] or "0.5" in alerts[0]
```

- [ ] **Step 2: Implement `src/common/report.py`**

```python
"""Per-run scrape report + snapshot-diff alerts.

Each scraper produces a ScrapeReport; `snapshot_diff` compares today's parsed
count against the median of the past N reports and emits alerts on big drops.
Used by CI to surface silently-broken scrapers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from src.common.logging import get_logger

log = get_logger("scrapers.report")

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


@dataclass
class ScrapeReport:
    """A single scraper's run summary."""

    source: str
    run_date: date
    products_in: int = 0
    products_parsed: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    error_count: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "run_date": self.run_date.isoformat(),
            "products_in": self.products_in,
            "products_parsed": self.products_parsed,
            "dropped": self.dropped,
            "error_count": self.error_count,
            "duration_seconds": self.duration_seconds,
        }

    def write(self, *, dir_: Path | None = None) -> Path:
        """Append this report as a JSON line in reports/<date>.jsonl."""
        target_dir = dir_ or REPORTS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        out = target_dir / f"{self.run_date.isoformat()}.jsonl"
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict()) + "\n")
        return out


def snapshot_diff(
    today: ScrapeReport,
    history: list[ScrapeReport],
    *,
    threshold: float = 0.25,
) -> list[str]:
    """Return a list of alert strings if today's count drops > threshold vs history median."""
    if not history:
        return []

    parsed_counts = sorted(r.products_parsed for r in history)
    n = len(parsed_counts)
    median = parsed_counts[n // 2] if n % 2 else (parsed_counts[n // 2 - 1] + parsed_counts[n // 2]) / 2

    if median == 0:
        return []

    drop_pct = (median - today.products_parsed) / median
    if drop_pct > threshold:
        return [f"{today.source}: parsed count dropped {drop_pct:.1%} (today: {today.products_parsed}, 7-day median: {median:.0f})"]
    return []
```

- [ ] **Step 3: Run tests + commit**

```
pytest tests/common/test_report.py -v
```
Expect: 5 passed.

```bash
git add src/common/report.py tests/common/test_report.py
git commit -m "$(cat <<'EOF'
add ScrapeReport + snapshot-diff alerts

Per-run report appended as JSON line to reports/<date>.jsonl.
snapshot_diff() returns alert strings when today's parsed count
drops > threshold vs 7-day median — CI uses these to fail loud
on silently-broken scrapers.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: BaseScraper ABC

**Files:**
- Create: `src/scrapers/base.py`
- Create: `tests/scrapers/test_base.py`

- [ ] **Step 1: Failing test**

Create `tests/scrapers/test_base.py`:
```python
"""Tests for the BaseScraper ABC."""

from datetime import date

import pytest

from src.common.report import ScrapeReport
from src.scrapers.base import BaseScraper


def test_subclass_must_implement_methods():
    class Incomplete(BaseScraper):
        source = "incomplete"

    with pytest.raises(TypeError):
        Incomplete()


def test_complete_subclass_instantiates():
    class Complete(BaseScraper):
        source = "complete"

        def discover_categories(self):
            return [("https://example.com/cat", "Cat")]

        def parse_listing(self, html):
            return ["https://example.com/p/1"]

        def parse_product(self, html, product_url, source_url, category):
            return {"product_url": product_url, "product_name": "X", "price": 1.0}

    s = Complete()
    assert s.source == "complete"
    assert isinstance(s.report, ScrapeReport)


def test_drop_increments_report_counters():
    class Complete(BaseScraper):
        source = "complete"
        def discover_categories(self): return []
        def parse_listing(self, html): return []
        def parse_product(self, html, product_url, source_url, category): return None

    s = Complete()
    s._drop("missing_price")
    s._drop("missing_price")
    s._drop("parse_error")
    assert s.report.dropped == {"missing_price": 2, "parse_error": 1}
```

- [ ] **Step 2: Implement `src/scrapers/base.py`**

```python
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
from typing import Optional

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
    ) -> Optional[dict]:
        """Given product page HTML, return a product dict or None to drop."""

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
        for category_url, category_name in self.discover_categories():
            try:
                listing_html = self.fetch(category_url)
            except RetryExhausted as e:
                self.log.error("listing_fetch_failed", url=category_url, error=str(e))
                self.report.error_count += 1
                continue

            for product_url in self.parse_listing(listing_html):
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

    def _drop(self, reason: str) -> None:
        self.report.dropped[reason] = self.report.dropped.get(reason, 0) + 1
```

- [ ] **Step 3: Run tests + commit**

```
pytest tests/scrapers/test_base.py -v
```
Expect: 3 passed.

```bash
git add src/scrapers/base.py tests/scrapers/test_base.py
git commit -m "$(cat <<'EOF'
add BaseScraper ABC with lifecycle + report tracking

Three abstract hooks: discover_categories, parse_listing, parse_product.
Base handles HTTP via httpx+tenacity, retries, structlog, ScrapeReport
counters, context-managed client lifecycle. Subclasses with JS needs
override fetch() to spin up Playwright lazily.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Pydantic ProductRecord (scraper-side)

This shape is already defined in `src/matching/models.py:ProductRecord`. We re-export from a scraper-friendly location and add a validation helper.

**Files:**
- Create: `src/scrapers/models.py`
- Create: `tests/scrapers/test_models.py`

- [ ] **Step 1: Failing test**

Create `tests/scrapers/test_models.py`:
```python
"""Tests for scraper-side ProductRecord validation helper."""

import pytest
from pydantic import ValidationError

from src.scrapers.models import RawProduct, validate_record


def test_minimal_raw_product():
    p = RawProduct(
        source="tullys",
        product_url="https://shop.tullynurseries.ie/p/1",
        product_name_raw="Acer palmatum",
        price_native=29.95,
    )
    assert p.source == "tullys"
    assert p.currency == "EUR"


def test_validate_record_accepts_minimum():
    record = {
        "source": "tullys",
        "product_url": "https://shop.tullynurseries.ie/p/1",
        "product_name_raw": "Acer palmatum",
        "price_native": 29.95,
    }
    p = validate_record(record)
    assert p.size is None  # nullable now — no fake "9 cm" defaults


def test_validate_record_rejects_missing_required():
    with pytest.raises(ValidationError):
        validate_record({"source": "tullys"})
```

- [ ] **Step 2: Implement `src/scrapers/models.py`**

```python
"""Scraper-side raw product record (pre-matching)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class RawProduct(BaseModel):
    """A raw product row produced by a scraper, before matching pipeline runs."""

    model_config = ConfigDict(extra="allow")

    source: str
    product_url: str
    source_url: Optional[str] = None
    category: Optional[str] = None
    product_name_raw: str
    price_native: Optional[float] = None
    currency: str = "EUR"
    size: Optional[str] = None
    stock: Optional[int] = None
    quantity_per_pack: int = 1
    img_url: Optional[str] = None
    description: Optional[str] = None


def validate_record(record: dict) -> RawProduct:
    """Validate a dict produced by a scraper. Raises ValidationError on failure."""
    return RawProduct.model_validate(record)
```

- [ ] **Step 3: Run + commit**

```
pytest tests/scrapers/test_models.py -v
```
Expect: 3 passed.

```bash
git add src/scrapers/models.py tests/scrapers/test_models.py
git commit -m "$(cat <<'EOF'
add scraper-side RawProduct + validate_record helper

All optional fields are nullable — no fake "9 cm" or "0" defaults.
Scrapers now fail loud (ValidationError) on missing required fields
instead of silently producing garbage.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Smoke test the foundation end-to-end

**Files:**
- Create: `tests/scrapers/test_base_e2e.py`

A tiny end-to-end test using a fake server (httpx mock) so we know the BaseScraper + http + report wiring is correct before any real scraper rewrite.

- [ ] **Step 1: Test**

Create `tests/scrapers/test_base_e2e.py`:
```python
"""End-to-end smoke: a fake scraper using BaseScraper + mocked httpx."""

from unittest.mock import MagicMock, patch

from src.scrapers.base import BaseScraper


class FakeScraper(BaseScraper):
    source = "fake"
    rate_limit_seconds = 0  # don't sleep in tests

    def discover_categories(self):
        return [("https://fake.example.com/cat1", "Cat1")]

    def parse_listing(self, html):
        return ["https://fake.example.com/p1", "https://fake.example.com/p2"]

    def parse_product(self, html, product_url, source_url, category):
        if "p2" in product_url:
            return None  # simulate a drop
        return {
            "source": "fake",
            "product_url": product_url,
            "product_name": "Fake plant",
            "price": 1.0,
        }


@patch("src.scrapers.http.httpx.Client.get")
def test_e2e_scrape(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200, text="<html>ok</html>", raise_for_status=lambda: None
    )
    with FakeScraper() as s:
        results = s.run()

    assert len(results) == 1  # p1 succeeded, p2 returned None
    assert s.report.products_in == 2
    assert s.report.products_parsed == 1
    assert s.report.dropped == {"parse_returned_none": 1}
```

- [ ] **Step 2: Run + commit**

```
pytest tests/scrapers/test_base_e2e.py -v
```
Expect: 1 passed.

```bash
git add tests/scrapers/test_base_e2e.py
git commit -m "$(cat <<'EOF'
add end-to-end smoke for BaseScraper + http + report wiring

Validates the contract: discover → fetch → parse_listing → fetch →
parse_product → drop or accumulate → report counts match. Uses a
mocked httpx so it's fast and offline.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase B — Cross-platform paths

### Task 7: Fix `storage.py` Windows-only paths

**Files:**
- Modify: `src/common/storage.py`
- Create: `tests/common/test_storage.py`

The current `data\\{source}\\…` literals break on Linux. Replace with `pathlib`.

- [ ] **Step 1: Failing test**

Create `tests/common/test_storage.py`:
```python
"""Tests for cross-platform path handling in storage.py."""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from src.common.storage import export_data_locally


def test_export_data_locally_dated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    table = [{"source": "test_source", "product_name": "X", "price": 1.0}]
    export_data_locally(table=table, dated=True)
    expected = tmp_path / "data" / "test_source" / f"{date.today().isoformat()}.parquet"
    assert expected.exists()
    df = pl.read_parquet(expected)
    assert df.height == 1
    assert "input_date" in df.columns


def test_export_data_locally_undated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    table = [{"source": "rhs", "id": 1, "name": "Acer"}]
    export_data_locally(table=table, dated=False)
    expected = tmp_path / "data" / "rhs.parquet"
    assert expected.exists()
```

- [ ] **Step 2: Implement the path fix**

Edit `src/common/storage.py` to replace the literal `\\` paths with `pathlib.Path`. The existing function:

```python
def export_data_locally(table: list[dict], dated: bool = True) -> None:
    df = pl.DataFrame(table)
    source = df.select(pl.first("source")).item()

    if dated:
        df = add_defaults_to_fields(df, field_name="product_code", default_value=None)
        df = add_defaults_to_fields(df, field_name="quantity", default_value=1)
        df = add_defaults_to_fields(df, field_name="input_date", default_value=datetime.date.today())
        file_path = Path("data") / source / f"{datetime.date.today().strftime('%Y-%m-%d')}.parquet"
    else:
        file_path = Path("data") / f"{source}.parquet"

    file_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Storing data to file '{file_path}'")
    pq.write_table(df.to_arrow(), file_path)
```

Add `from pathlib import Path` to the imports. Remove the old Windows-style literal lines.

- [ ] **Step 3: Run + verify all existing scrapers still produce parquets in `data/<source>/<date>.parquet`**

```
pytest tests/common/test_storage.py -v
```
Expect: 2 passed.

Also verify the existing scrapers still work by inspecting one nursery's existing dated parquet directory hasn't been broken — just `ls data/tullys/` should still show the old files.

- [ ] **Step 4: Commit**

```bash
git add src/common/storage.py tests/common/test_storage.py
git commit -m "$(cat <<'EOF'
use pathlib for parquet paths (cross-platform fix)

Replaces Windows-only `data\\{source}\\…` literal paths with
pathlib.Path / so the same code runs on Linux CI. parents=True
creates intermediate dirs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase C — Reference rewrite

### Task 8: Rewrite gardens4you on BaseScraper

**Files:**
- Modify: `src/scrapers/gardens4you.py` (full rewrite)
- Create: `tests/fixtures/cassettes/gardens4you_listing.yaml` (VCR cassette)
- Create: `tests/fixtures/cassettes/gardens4you_product.yaml` (VCR cassette)
- Create: `tests/scrapers/test_gardens4you.py`

The current `gardens4you.py` has a `raise Exception(f"NOT FOUND...")` at line 30 that crashes the whole scrape on a single bad product. The rewrite kills that hard-fail and uses BaseScraper's drop-and-continue pattern.

- [ ] **Step 1: Capture VCR cassettes**

Run a one-off script to record one listing page + one product page:
```python
# scripts/record_gardens4you_cassettes.py
from pathlib import Path
import vcr

OUT = Path("tests/fixtures/cassettes")
OUT.mkdir(parents=True, exist_ok=True)

with vcr.use_cassette(OUT / "gardens4you_listing.yaml"):
    import httpx
    httpx.get("https://www.gardens4you.ie/garden-plants/perennials/").raise_for_status()

with vcr.use_cassette(OUT / "gardens4you_product.yaml"):
    httpx.get("https://www.gardens4you.ie/garden-plants/perennials/heuchera-marmalade-a14523.html").raise_for_status()
```

Run it once. The cassettes get committed.

- [ ] **Step 2: Write tests using the cassettes**

Create `tests/scrapers/test_gardens4you.py`:
```python
"""VCR-backed regression tests for gardens4you scraper."""

from pathlib import Path

import pytest

from src.scrapers.gardens4you import Gardens4YouScraper

CASSETTES = Path(__file__).resolve().parents[1] / "fixtures" / "cassettes"


@pytest.mark.vcr(cassette_library_dir=str(CASSETTES))
def test_parse_listing_returns_urls():
    scraper = Gardens4YouScraper()
    with open(CASSETTES / "gardens4you_listing_html.html", encoding="utf-8") as f:
        html = f.read()
    urls = scraper.parse_listing(html)
    assert len(urls) > 0
    assert all(u.startswith("https://www.gardens4you.ie") for u in urls)


@pytest.mark.vcr(cassette_library_dir=str(CASSETTES))
def test_parse_product_returns_record():
    scraper = Gardens4YouScraper()
    with open(CASSETTES / "gardens4you_product_html.html", encoding="utf-8") as f:
        html = f.read()
    record = scraper.parse_product(
        html,
        product_url="https://www.gardens4you.ie/garden-plants/perennials/heuchera-marmalade-a14523.html",
        source_url="https://www.gardens4you.ie/garden-plants/perennials/",
        category="Perennials",
    )
    assert record is not None
    assert record["source"] == "gardens4you"
    assert "product_name" in record or "product_name_raw" in record
    assert record["price_native"] is not None or record["price"] is not None


def test_parse_product_returns_none_on_garbage():
    scraper = Gardens4YouScraper()
    record = scraper.parse_product(
        "<html>not a product page</html>",
        product_url="https://www.gardens4you.ie/garbage",
        source_url="https://www.gardens4you.ie/",
        category="x",
    )
    assert record is None  # graceful drop, NOT raise Exception
```

- [ ] **Step 3: Rewrite `src/scrapers/gardens4you.py`**

Replace the whole file with a `Gardens4YouScraper(BaseScraper)` implementation. Key changes from the legacy version:
- Subclasses `BaseScraper`
- `discover_categories` reads `config.gardens4you.data_sources`
- `parse_listing(html)` returns product URLs
- `parse_product(...)` returns dict OR None — never raises
- Uses `self.fetch(...)` instead of `session.get(...)`
- The `extract_size_from_url` function's `raise Exception` block is replaced with `return None` (and logged)
- All hardcoded fallbacks (`"Bare Root"` for unknown size) removed — `size = None` instead
- Module-level `session = HTMLSession()` global is gone — use the BaseScraper's HTTP client

For backward compatibility with `load_bronze_data.py`, keep a `get_product_data()` shim function:
```python
def get_product_data(config_file_name: str = "gardens4you") -> list[dict]:
    """Backward-compat shim — runs the new scraper and returns the legacy format."""
    with Gardens4YouScraper() as scraper:
        return scraper.run()
```

- [ ] **Step 4: Run tests**

```
pytest tests/scrapers/test_gardens4you.py -v
```
Expect: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/scrapers/gardens4you.py tests/scrapers/test_gardens4you.py tests/fixtures/cassettes/
git commit -m "$(cat <<'EOF'
rewrite gardens4you on BaseScraper; remove hard-fail and silent fallbacks

- Subclasses BaseScraper (httpx + tenacity + structlog + report counters)
- The line-30 `raise Exception("NOT FOUND…")` that crashed the whole
  scrape on one bad product is gone — drops and continues now
- Hardcoded `"Bare Root"` size fallback removed; size is now nullable
- Module-level HTMLSession global removed
- VCR cassette fixtures committed for regression coverage

Backward-compat shim get_product_data() preserves load_bronze_data.py
integration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase D — New nursery scrapers

### Task 9: Hedging.ie scraper (top value pick — free delivery)

**Files:**
- Create: `src/scrapers/hedgingie.py`
- Create: `config/hedgingie.py` (URL list per category)
- Modify: `config/nurseries.yaml` (add hedgingie entry)
- Modify: `load_bronze_data.py` (add hedgingie to choices)
- Create: `tests/fixtures/cassettes/hedgingie_*.{yaml,html}`
- Create: `tests/scrapers/test_hedgingie.py`

- [ ] **Step 1: Probe site to confirm it's scrapeable**

```
.venv/Scripts/python.exe -c "import httpx; r = httpx.get('https://www.hedging.ie/', follow_redirects=True); print('status:', r.status_code, 'len:', len(r.text), 'cf:', 'cloudflare' in r.text.lower())"
```

If status=200 and no Cloudflare challenge, proceed. If blocked (status=403 or Cloudflare page), report BLOCKED and we'll route via self-hosted runner later (don't try to scrape from CI).

- [ ] **Step 2: Identify category URLs**

Inspect the site's category structure in a browser. Common pattern: `/category/<slug>/`. Hand-pick 5-10 categories (Hedging Plants, Trees, Shrubs, Perennials, etc.) and put them in `config/hedgingie.py`:
```python
data_sources = [
    ("https://www.hedging.ie/product-category/hedging/", "Hedging"),
    ("https://www.hedging.ie/product-category/trees/", "Trees"),
    # ... etc
]
```

- [ ] **Step 3: Capture cassettes for one listing + one product**

Same pattern as Task 8 — record one of each.

- [ ] **Step 4: Write tests + scraper**

Following the BaseScraper pattern from gardens4you:
- `class HedgingIeScraper(BaseScraper)` with `source = "hedgingie"`
- Implement the three hooks
- Inspect the cassette HTML to find the right CSS selectors for product cards / price / stock / size

- [ ] **Step 5: Add to nurseries.yaml + load_bronze_data.py**

In `config/nurseries.yaml`:
```yaml
hedgingie:
  display_name: "Hedging.ie"
  base_url: https://www.hedging.ie
  currency: EUR
  vat_included: true
  delivery_type: free
  delivery_fees: []
  min_order_eur: 0
  runs_on: github-actions
  ships_live_plants_to_ireland: true
  notes: "Free delivery — top value pick from research."
```

In `load_bronze_data.py`, add `"hedgingie"` to the `--site` choices and a `case "hedgingie":` branch.

- [ ] **Step 6: Run tests + commit**

```
pytest tests/scrapers/test_hedgingie.py -v
```

```bash
git add src/scrapers/hedgingie.py config/hedgingie.py config/nurseries.yaml load_bronze_data.py tests/scrapers/test_hedgingie.py tests/fixtures/cassettes/hedgingie*
git commit -m "$(cat <<'EOF'
add Hedging.ie scraper (free delivery, top value pick)

Identified in sub-project R research as standout for free shipping.
Built on BaseScraper. VCR cassettes committed for regression coverage.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: David Austin EU scraper (must use eu.davidaustinroses.com per research)

**Files:**
- Create: `src/scrapers/david_austin.py`
- Create: `config/david_austin.py`
- Modify: `config/nurseries.yaml`
- Modify: `load_bronze_data.py`
- Create: `tests/fixtures/cassettes/david_austin_*`
- Create: `tests/scrapers/test_david_austin.py`

Same pattern as Task 9. KEY: base URL is `https://eu.davidaustinroses.com` (the `.com` doesn't ship to IE — only the `.eu` does, per research).

In nurseries.yaml:
```yaml
david_austin:
  display_name: "David Austin Roses (EU)"
  base_url: https://eu.davidaustinroses.com
  currency: EUR
  vat_included: true
  delivery_type: flat
  delivery_fees: [{ max_value_eur: null, fee_eur: 9.95 }]
  min_order_eur: 0
  runs_on: github-actions
  ships_live_plants_to_ireland: true
  notes: "MUST use eu.davidaustinroses.com — the .com site does not ship to IE."
```

Commit:
```
add David Austin Roses (EU) scraper

Premier rose specialist; per sub-project R research, MUST use the .eu
domain — .com does not ship to Ireland. Built on BaseScraper. VCR
cassettes committed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## Phase E — Integration smoke

### Task 11: Run gardens4you + hedgingie + david_austin via the orchestrator

- [ ] **Step 1: Smoke test each new scraper produces a parquet**

```
.venv/Scripts/python.exe load_bronze_data.py --site gardens4you
.venv/Scripts/python.exe load_bronze_data.py --site hedgingie
.venv/Scripts/python.exe load_bronze_data.py --site david_austin
```

For each: a fresh dated parquet should appear under `data/<source>/<date>.parquet`. Schema should match the new RawProduct shape (no fake `"9 cm"` defaults; size nullable).

If a real-network run fails (anti-bot, transient timeouts), that's fine — log it and move on. The point of this task is to confirm the pipeline runs end-to-end.

- [ ] **Step 2: Re-run the matching pipeline against the augmented product set**

```
.venv/Scripts/python.exe load_bronze_data.py --matching --no-llm
```

The new nurseries' products should appear in `data/products_matched.parquet`. Confirm:
```
.venv/Scripts/python.exe -c "
import polars as pl
df = pl.read_parquet('data/products_matched.parquet')
print(df.group_by('source').agg(pl.len()).sort('len', descending=True))
"
```

- [ ] **Step 3: Commit any updated parquets**

```bash
git add data/
git commit -m "$(cat <<'EOF'
seed parquets from first BaseScraper-driven runs

gardens4you (rewritten), hedgingie, david_austin — each produced a
fresh dated parquet. products_matched.parquet refreshed to include
the new sources.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Final pytest sweep

- [ ] **Step 1: Run all tests**

```
.venv/Scripts/python.exe -m pytest -v 2>&1 | tail -10
```

Expect: all tests pass (the existing 83 from sub-project 2 + the new ~25 from sub-project 1 = ~108 tests).

- [ ] **Step 2: If anything's red, fix in-place. Commit any fixes.**

---

## Out of scope for sub-project 1

- Rewrites of arboretum, carragh, quickcrop, tullys, rhs scrapers (each is a follow-up PR following the gardens4you template)
- Adding the remaining 6 nurseries from research (Future Forests, Newlands, Mr Middleton, Brown Envelope, Caragh extras, etc.) — same pattern, same effort per nursery
- Selenium → Playwright migration (deferred until each Selenium scraper is rewritten)
- Removing requests-html entirely (must wait until all scrapers using it are rewritten)
- Anti-bot defences (proxies, residential IP rotation) — reactive, only added if a specific nursery requires it

---

## Self-review checklist

- [ ] All 12 tasks ticked
- [ ] `pytest -v` shows ~108 passed, 0 failed
- [ ] `data/gardens4you/<date>.parquet`, `data/hedgingie/<date>.parquet`, `data/david_austin/<date>.parquet` exist and load cleanly
- [ ] `data/products_matched.parquet` includes all three sources
- [ ] No file references `requests_html` import outside of the not-yet-rewritten scrapers (arboretum, carragh, quickcrop, tullys, rhs)
- [ ] `src/common/storage.py` uses `pathlib.Path`, not `\\` literals
