# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Plant price comparison for Irish/UK/EU online nurseries. Scrapers produce per-nursery parquets under `data/<source>/data.parquet`; a matching pipeline joins them to an RHS plant dictionary at `data/rhs/data.parquet`; a wishlist optimiser (still being built — see `docs/superpowers/specs/2026-05-13-wishlist-optimizer-design.md`) picks the cheapest nursery-subset plan for a desired plant list.

Scrapers run **locally only**, no CI scraping. The freshness gate (30 days by default) skips a site whose newest parquet is recent.

## Commands

```
# Install (Windows PowerShell)
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Scrape one nursery (respects 30-day freshness gate)
python load_bronze_data.py --site tullys
python load_bronze_data.py --site tullys --force          # bypass gate
$env:FORCE_SCRAPE=1; python load_bronze_data.py --site tullys  # alt bypass
$env:SCRAPE_MAX_AGE_DAYS=7; python load_bronze_data.py --site tullys  # tighter window

# Scrape every nursery in parallel
python scripts/scrape_all.py                              # default -j 3
python scripts/scrape_all.py -j 5 --force
python scripts/scrape_all.py --sites tullys,quickcrop
python scripts/scrape_all.py --list-sites

# Refresh RHS dictionary (two stages, the second resumable via sqlite staging)
python load_bronze_data.py --site rhs_urls
python load_bronze_data.py --site rhs

# Run the deterministic + LLM matching pipeline
python run_matching.py                                    # idempotent: skips if output newer than inputs
python run_matching.py --force                            # re-run regardless
python run_matching.py --no-llm                           # deterministic only

# Tests + lint (CI runs both)
pytest -v
pytest tests/scrapers/test_tullys.py                      # one file
pytest tests/scrapers/test_tullys.py::test_parse_product  # one test
ruff check .
ruff check --fix .
```

VS Code tasks in `.vscode/tasks.json` wrap the common scrape/match invocations.

## Architecture

### Data flow

`scrape -> per-nursery scrape parquet -> match -> per-nursery matched parquet -> concat -> products_matched.parquet`

- `load_bronze_data.py` — single entry point per nursery (`--site <slug>`). Match-statement dispatches to `src/scrapers/<slug>.py`. Before scraping it calls `should_scrape()` (the freshness gate). Output via `export_data_locally()` lands at `data/<source>/data.parquet`.
- `run_matching.py` — picks each nursery's latest scrape parquet from `data/<slug>/`, runs the deterministic + LLM pipeline once cross-nursery on the changed set (preserves prompt-cache efficiency), then writes per-nursery intermediates at `data/<slug>/matched.parquet` and concatenates them into `data/products_matched.parquet`. Per-nursery skip-if-newer is built in (intermediate vs scrape parquet vs RHS mtime); use `--force` to re-match everything.
- `scripts/scrape_all.py` — runs `load_bronze_data.py` per site in a `ThreadPoolExecutor`, with one structlog file per site at `logs/<site>.log`.

### Single sources of truth

- **Which nurseries are scraped today** — `config/nurseries.yaml` entries with `runs_on: github-actions`. Read via `src.common.nurseries.scraped_nursery_slugs()`. Used by the freshness gate, the matching loop, and `scripts/scrape_all.py`. Adding a scraper requires both adding to `src/scrapers/`, importing in `load_bronze_data.py`, adding a `match` arm, AND adding the yaml entry.
- **Per-nursery metadata** — `config/nurseries.yaml`. Pydantic models in `src/common/nurseries.py`. Fields drive VAT handling, FX, and shipping calculations downstream.
- **VAT handling** — `src.common.storage._apply_vat_if_needed()` reads `vat_included` from the yaml and bakes 23% IE VAT into ex-VAT sources at write time. If config loading fails for an ex-VAT source the write is aborted (a silent VAT skip caused wrong Tullys prices once).

### Scrapers (`src/scrapers/`)

All site-specific scrapers subclass `BaseScraper` (`src/scrapers/base.py`) and implement three abstract methods:

- `discover_categories() -> [(url, name), ...]`
- `parse_listing(html) -> [product_url, ...]`
- `parse_product(html, product_url, source_url, category) -> dict | list[dict] | None`

`BaseScraper.run()` orchestrates the lifecycle: dedup product URLs across categories, call `parse_product` for each, accumulate rows, and track a `ScrapeReport` (in/parsed/dropped/errors). HTTP retries live in `src/scrapers/http.py` (httpx + tenacity, `RetryExhausted` on exhaustion). Override `fetch()` if the site needs JS rendering.

Shared platform helpers (`shopify_json.py`, `magento_graphql.py`, `bigcommerce_sitemap.py`, `woocommerce_store.py`) provide reusable extraction for nurseries that share a commerce stack. `concurrent.py` is the async/HTTPX helper for scrapers with many product fetches.

### Matching (`src/matching/`)

`run.run_with_llm_fallback()` is the production entry. Pipeline:

1. **Overrides** — `match_overrides.parquet` cache wins first. Source `manual` keeps `match_method="manual_override"`; LLM-written entries become `"llm"`.
2. **gnparser** (`gnparser_wrap.py`) — parses scientific names.
3. **classify** (`classify.py`) — decides `is_plant` / `product_category`.
4. **exact** (`exact.py`) — `RhsIndex` lookup if gnparser succeeded.
5. **fuzzy** (`fuzzy.py`) — rapidfuzz against pre-built RHS candidates at threshold 0.85. Runs even if parse failed (catches genus + cultivar strings). A fuzzy hit promotes `is_plant=True`.
6. **LLM fallback** — only the residual `match_method == "unmatched"` is sent to Claude Haiku (`claude-haiku-4-5-20251001`) in batches of 50, using prompt-cached RHS candidates. New decisions are persisted back into the overrides parquet, then the deterministic pipeline re-runs so the overrides apply.

`ANTHROPIC_API_KEY` is required for the LLM step; use `--no-llm` to skip.

### Transforms (`src/transforms/`)

Runs after matching. `size_normalize.add_size_columns()` extracts numeric size + pot-code info from product names/variants and is currently the only post-match step in `run_matching.py`.

### Wishlist (`src/wishlist/`)

Optimiser core. `sizes.py` is the cm + pot-code lookup tables used to compare product sizes across nurseries. The Streamlit UI mentioned in the README (`scripts/wishlist.py`) is not yet present — track the design spec at `docs/superpowers/specs/2026-05-13-wishlist-optimizer-design.md`.

### Logging

`src.common.logging` (structlog). Both `load_bronze_data.py` and `run_matching.py` call `configure(source=..., force=True)` at startup so each scrape subprocess writes its own `logs/<source>.log`. `scripts/scrape_all.py` relies on this — it suppresses subprocess stdout/stderr and only watches exit codes.

## Conventions that aren't obvious from the code

- **Tipperary is the default shipping zone.** For any nursery with `delivery_type: tiered` (or zoned rates), record the Tipperary rate in `nurseries.yaml` (see the comment at the top of that file).
- **Full coverage for scrapers.** A new scraper must walk every product link, not a curated master-listing subset — verify exhaustiveness before shipping.
- **Concurrent fetches when N is large.** Scrapers that hit >200 product pages should use async/HTTPX (`src/scrapers/concurrent.py`), not serial + `time.sleep`.
- **Idempotent pipelines.** Both `load_bronze_data.py` (via freshness gate) and `run_matching.py` (via mtime check) skip when re-run with fresh outputs. Always favour adding a similar gate when introducing new long-running steps; `--force` is the escape hatch.
- **Polars 1.x.** Pinned `>=1.40,<2` in requirements.txt. On Windows + uv-managed Python, `tzdata` is required for `zoneinfo` (Polars 1.x uses it for datetime serialization) and is in requirements.txt for that reason.
- **CI runs `ruff check .` then `pytest -v`** on Python 3.11 — see `.github/workflows/ci.yml`. Scrapers do not run in CI; only tests do.
