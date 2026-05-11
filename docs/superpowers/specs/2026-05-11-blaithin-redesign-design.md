# Blaithin Redesign — Design Spec

**Status:** Draft for user review
**Date:** 2026-05-11
**Owner:** Andrew Burns
**Decisions captured from:** `docs/superpowers/brainstorm/2026-05-11-redesign-questions.md`

---

## 1. Problem statement

The current system spans two repos:

- **`blaithin_files`** — Python scrapers for 5 Irish nurseries + RHS, outputting parquet snapshots committed to git.
- **`blaithin`** — Mage AI in Docker → BigQuery + dbt → Looker Studio dashboard, pulling parquets from the first repo over GitHub raw URLs.

Three structural problems:

1. **Scrapers are fragile.** No retries, no rate limiting, no logging, no tests, hardcoded fallback values that mask data loss (`size = "9 cm"` if parsing fails), driver leaks, ad-hoc Unicode patches in `rhs.py`. Recent commit history is mostly "fix grasses / fix bot names / fix rhs data" — patch-fix cycles.
2. **Matching collapses cultivar information.** `combine_common_and_botanical_names.py` flattens RHS botanical + common names into one column; the Levenshtein matcher in `match_product_to_plant.py` then maps every cultivar of a species onto the same RHS row. "Acer palmatum 'Bloodgood'", "'Atropurpureum'", and "'Sango Kaku'" all collapse onto plain "Acer palmatum". Synonyms are actively discarded at `rhs.py:34`.
3. **Hosting costs money and lives in two places.** Looker Studio is free but BigQuery + GCS are not, and the dashboard cannot evolve in-repo with the data.

Plus surfacing problems: no flagging of non-plant SKUs (compost, tools, pots), no delivery fees / min-orders, no currency normalization for cross-border nurseries.

---

## 2. Goals & non-goals

### Goals

- One repo, free hosting (GitHub Pages).
- Robust scraping: retries, structured logging, validation, no silent data loss, per-run report.
- Cultivar-preserving matching with deterministic-first + LLM-fallback strategy and an auditable cache.
- Add three new nurseries: Farmer Gracy (UK→IE, bare-root), Bulbi.nl (NL bulbs/perennials), GreenGardenFlowerBulbs.nl (NL bulk bulbs).
- Categorize non-plant SKUs (Compost, Tools, Pots, Fertiliser, etc.) and surface them as their own filterable comparison.
- Show delivery fees, min orders, VAT-applicability per nursery.
- Drill-down dashboard with sortable tables and embedded links to RHS pages and nursery product pages.

### Non-goals

- Per-cultivar RHS data (RHS rarely publishes it; we keep RHS at species level and let cultivar live on the product row).
- Real-time stock updates (daily refresh is fine).
- User accounts, wishlists, price-drop alerts (post-MVP).
- Mobile-first design (responsive is enough).

---

## 3. Architecture overview

```
                              ┌──────────────────────────────────┐
                              │ GitHub repo: blaithin (single)   │
                              │                                  │
  scheduled GHA ──daily──►    │  src/scrapers/   (per-site)      │
  (or self-hosted runner      │  src/matching/   (gnparser+LLM)  │
   for blocked sites)         │  src/transforms/ (Polars/DuckDB) │
                              │  site/           (Observable)    │
                              │  data/           (parquets)      │
                              │  config/         (per-nursery)   │
                              └────────────────┬─────────────────┘
                                               │
                                               ▼
                                     GitHub Pages (free)
                                     DuckDB-WASM in browser
```

**Single language stack:** Python for scraping/matching/transforms; Observable Framework (JS/Markdown) for the dashboard.

**Storage:** parquets committed to git (already established pattern; small files; great diff-ability for review of LLM matches).

**Orchestration:** GitHub Actions cron — see §10 for the bot-detection nuance.

---

## 4. Sub-project order (per Q4 decision: D2)

| # | Sub-project | Approx. days | Unblocks |
|---|---|---|---|
| 0 | Repo consolidation | 1 | All |
| R | Nursery research (vetted candidate list) | 0.5 (one-off, but maintained) | 1 |
| 2 | Matching v2 + data model | 4–6 | 1, 3 (defines schema) |
| 1 | Scraping hardening + new sites | 5–8 | 3, 4 |
| 3 | Dashboard | 4–6 | 4 |
| 4 | Observability + tests + CI | 2 | — |

Total: **~3–4 weeks** focused work. Sub-project 1 is largest because of new-nursery scrapers (count determined by §5.5 research output) plus base hardening. Sub-project R runs in parallel with sub-project 0.

---

## 5. Sub-project 0 — Repo consolidation

**Outcome:** single repo containing scrapers, matching, transforms, dashboard. Existing scraping continues to work unchanged on day 0.

**Steps:**

1. New top-level layout in `blaithin_files` (we'll keep the repo name to avoid renaming GitHub URLs):
   ```
   src/
     scrapers/      # was bronze/
     matching/      # new (will replace blaithin/transformers/)
     transforms/    # new (will replace dbt models)
     common/        # shared utils
   config/          # already exists
   data/            # already exists (parquets)
   site/            # new — Observable Framework dashboard
   .github/
     workflows/
   docs/
     superpowers/
   ```
2. Move `bronze/` → `src/scrapers/`, `cloud_storage/` → `src/common/storage.py`.
3. Copy matching code from sister repo (`blaithin/docker/blaithin/transformers/*.py`) into `src/matching/legacy.py` as a reference (will be replaced in sub-project 2).
4. Copy `rhs.parquet`, `rhs_urls.parquet`, the latest dated parquet per nursery from sister repo into `data/` (we already have everything authoritative in this repo).
5. Delete from sister repo: Terraform, `docker/`, dbt configs, GCS exporters, BigQuery loaders. Leave a `MIGRATED.md` pointing here.
6. Update `requirements.txt` (will grow significantly in later sub-projects).

**Success criteria:** `python -m src.scrapers.tullys` (or equivalent) runs and writes a parquet, behaving identically to today.

---

## 5.5 Sub-project R — Nursery research

**Outcome:** a maintained markdown directory of online nurseries that ship to Ireland, used to drive selection of which sites to scrape next. Lives at `docs/research/nurseries-ireland-shipping.md` and is referenced from this spec.

**What it captures, per nursery:**

- Name, URL, country, currency.
- Specialty (bare-root, bulbs, roses, hedging, perennials, vegetables, indoor, etc.).
- **Ships to Ireland** — yes / no / restricted (Brexit phytosanitary rules mean many UK nurseries now only ship seeds, bulbs, or dormant material, not live potted plants — recorded explicitly per nursery).
- Delivery cost, min order, VAT applicability.
- Value reputation (cheap / mid / premium) with one-line reason.
- Anti-bot risk if visible (Cloudflare? Shopify? plain WooCommerce?) — informs the runner-profile decision in §10.
- Notes (sales calendar, bare-root season, awards).

**Initial pass:** the user has named three additions explicitly (Farmer Gracy, Bulbi.nl, GreenGardenFlowerBulbs.nl). The research pass adds a comprehensive set of additional candidates across IE/UK/EU and per specialty.

**Selection criterion for sub-project 1:** scrape priority = `(value_reputation × delivery_to_ireland_quality × anti_bot_risk_inverse)`. We do not commit to scraping all candidates — the directory is a menu. New scrapers can be added incrementally after sub-project 1's `BaseScraper` foundation is in place; each new nursery is a small, well-scoped PR.

**Maintenance:** the file is a living document. When a nursery starts/stops shipping to Ireland, or pricing/delivery changes materially, the research file gets updated. Stale entries (>12 months unchecked) get re-verified.

**Success criteria:**

- ≥ 30 nurseries reviewed across IE/UK/EU.
- Every entry has a verified "ships to Ireland" status.
- Specialty index lets a reader find "best for bare-root hedging" or "best for bulbs in bulk" in one lookup.
- The list of sites we actually scrape in sub-project 1 is justified by reference to this file.

---

## 6. Sub-project 2 — Matching v2 + data model

This is the heart of the redesign. Three components: data-model rework, two-stage matcher, non-plant classifier.

### 6.1 Data-model rework

**RHS table** (`data/rhs.parquet`) — new shape:

| column | type | notes |
|---|---|---|
| `rhs_id` | int | from RHS |
| `genus` | str | parsed from botanical_name via gnparser |
| `species` | str | parsed |
| `botanical_name` | str | canonical (genus + species, no cultivar) |
| `common_names` | list[str] | array, was previously a single column |
| `synonyms` | list[str] | **new** — currently discarded at `rhs.py:34` |
| `plant_type` | list[str] | unchanged |
| `family` | str | unchanged |
| `description`, `height`, `spread`, `soils`, `moisture`, `ph`, `sun_exposure`, `aspect`, `exposure`, `hardiness`, `foliage`, `habit` | (mostly unchanged) | unchanged |
| `is_rhs_award_winner`, `is_pollinator_plant` | bool | unchanged |
| `plant_url` | str | unchanged |

One row per `(genus, species)`. Cultivar-level RHS pages are currently rare and inconsistent; if we encounter one we record the cultivar in `synonyms` for matching purposes only.

**Product table** (`data/products.parquet`) — augmented:

| column | type | notes |
|---|---|---|
| `source` | str | "tullys", "arboretum", "farmer_gracy", "bulbi", "greengardenflowerbulbs", etc. |
| `product_url` | str | for dashboard linking |
| `source_url` | str | category page |
| `category` | str | nursery's own category |
| `product_name_raw` | str | as-scraped |
| `product_name_clean` | str | normalized |
| `genus` | str | parsed |
| `species` | str | parsed |
| `cultivar` | str | **new** — parsed (e.g., "Bloodgood") |
| `cultivar_group` | str | **new** — parsed (e.g., "Atropurpureum Group") |
| `rhs_id` | int | matched (nullable) |
| `match_method` | str | one of: `url_field`, `gnparser_exact`, `rapidfuzz`, `llm`, `manual_override`, `unmatched` |
| `match_confidence` | float | 0..1 |
| `is_plant` | bool | **new** — false for tools/pots/composts/etc. |
| `product_category` | str | **new** — `plant`, `bulb`, `seed`, `compost`, `soil`, `tool`, `pot`, `fertiliser`, `accessory`, `other` |
| `price_native` | float | as-scraped |
| `currency` | str | "EUR", "GBP" |
| `price_eur` | float | normalized for sorting/comparison |
| `size` | str | nullable (no more "9 cm" defaults) |
| `pot_size_litres` | float | nullable, parsed where possible |
| `stock` | int | nullable |
| `quantity_per_pack` | int | default 1 |
| `img_url` | str | nullable |
| `description` | str | nullable |
| `input_date` | date | snapshot date |

**Match overrides table** (`data/match_overrides.parquet`) — **new**, human-auditable:

| column | type | notes |
|---|---|---|
| `product_name_clean` | str | the input string |
| `rhs_id` | int | the resolved RHS id (nullable if "no match exists") |
| `cultivar` | str | parsed cultivar |
| `is_plant` | bool | classification |
| `product_category` | str | classification |
| `source` | str | `llm`, `manual` |
| `model` | str | `claude-haiku-4-5` etc. |
| `created_at` | datetime | |
| `notes` | str | optional human comment |

**Nursery metadata** (`config/nurseries.yaml`) — **new**:

```yaml
tullys:
  display_name: "Tully's Nurseries"
  base_url: https://shop.tullynurseries.ie
  currency: EUR
  vat_included: true
  delivery:
    type: tiered            # flat | tiered | by_weight | quote_only
    fees:
      - max_value_eur: 100
        fee_eur: 12
      - max_value_eur: null
        fee_eur: 0          # free over 100
  min_order_eur: 0
  notes: ""
farmer_gracy:
  display_name: "Farmer Gracy"
  base_url: https://www.farmergracy.co.uk
  currency: GBP
  vat_included: true        # at IE checkout
  delivery:
    type: flat
    fees: [{ max_value_eur: null, fee_eur: 6.95 }]
  min_order_eur: 0
  notes: "Specialises in bare-root, often cheapest for those."
bulbi:
  display_name: "Bulbi.nl"
  base_url: https://www.bulbi.nl
  currency: EUR
  vat_included: false       # consumer-side; VAT may apply at IE customs
  delivery:
    type: tiered
    fees:                   # to be filled in from site
      - max_value_eur: 50
        fee_eur: 12
  min_order_eur: 25
  notes: "VAT may apply on import to Ireland."
# ... etc
```

The dashboard reads this config and renders delivery/VAT badges next to prices. Currency normalization uses ECB daily rates cached in `data/fx.parquet`.

### 6.2 Two-stage matcher (B3)

```
product (raw scraped row)
  │
  ▼
[1] product_name_clean ← normalize: strip pot codes, sizes, qty packs
[2] try url_field      ← if scraper extracted a structured botanical name from URL/page, use it
[3] try gnparser       ← parse {genus, species, cultivar, group}
[4] exact lookup       ← (genus, species) → rhs_id, cultivar kept on product row
[5] rapidfuzz residual ← fuzzy on rhs.synonyms + rhs.botanical_name + rhs.common_names, threshold ≥ 0.85
[6] match_overrides    ← lookup in cache
[7] LLM batch          ← unmatched residual → Claude Haiku 4.5 → write to match_overrides
[8] still unmatched    ← `match_method = "unmatched"`, surfaced in a "needs review" table
```

**Modules:**

- `src/matching/normalize.py` — strips known nursery cruft (`r"\d+\s*(cm|ltr|litre|L|P\d+)"`, `r"\([^)]+\)$"`, etc.).
- `src/matching/gnparser.py` — wrapper around `pygnparser` (Python binding to Global Names Parser, MIT licensed). Returns `{genus, species, cultivar, group, rank}`.
- `src/matching/exact.py` — joins parsed names against the RHS table.
- `src/matching/fuzzy.py` — rapidfuzz residual.
- `src/matching/llm.py` — batches unmatched names, calls Claude Haiku with prompt caching (RHS list as cached prefix), parses JSON response, writes to match_overrides.
- `src/matching/run.py` — orchestrates the pipeline, emits a per-run report.

**LLM prompt shape** (Haiku 4.5 with prompt caching on the static RHS list):

```
SYSTEM (cached): You are a botanical matcher. Given a list of RHS plant
records (id, genus, species, common_names, synonyms) and a list of
unmatched product strings from Irish/UK nurseries, return JSON mapping
each product to {rhs_id, cultivar, is_plant, product_category, confidence, reasoning}.
- If the product is not a plant (e.g., compost, tools), set is_plant=false
  and product_category to one of: bulb|seed|compost|soil|tool|pot|fertiliser|accessory|other.
- For plants, parse cultivar from quotes if present.
- If no RHS record matches at species level, set rhs_id=null.
RHS records: <large JSON, cached>

USER: Match these products: <list>
```

Prompt-cache hit on the RHS list (~5MB compressed → ~1M tokens) drops cost on subsequent runs to ~0.10× — pennies per delta. Only unmatched products go through the LLM, and once cached in `match_overrides.parquet`, never re-run unless the product string changes.

### 6.3 Non-plant classification

The same LLM call (or a deterministic prefilter) tags `is_plant` and `product_category`. Deterministic prefilter checks:

- name matches `r"\b(compost|fertili[sz]er|spray|soil|gravel|stake|cane|tie|secateur|fork|spade|rake|wheelbarrow|pot|planter|tray|module|plug|seed packet|cloche|fleece|net)\b"` → likely non-plant.
- gnparser successfully parsed a genus → likely plant.

LLM only sees ambiguous cases. Reduces LLM volume further.

### 6.4 Success criteria

- ≥ 95% of historical product rows resolve to a non-null `rhs_id` OR a non-plant `product_category`.
- Manual spot-check of 50 cultivar-bearing names: cultivar correctly extracted in ≥ 90%.
- The `unmatched` table has < 100 rows after LLM pass on a full historical replay.
- Match overrides file is committed to git and human-readable.

---

## 7. Sub-project 1 — Scraping hardening + new sites

### 7.1 Shared base (per Q1 decision: A2)

`src/scrapers/base.py` introduces:

- `class BaseScraper(ABC)`:
  - `fetch(url) -> str` — uses `httpx` (sync) with `tenacity` exponential-backoff retries on 429/5xx/timeouts.
  - `fetch_js(url) -> str` — uses `playwright` (replaces both Selenium and `requests-html`) when JS rendering needed.
  - context-managed lifetime (`with TullysScraper() as s: ...`) ensuring driver/session cleanup on errors.
  - `parse_listing(html) -> list[ProductRef]` — abstract.
  - `parse_product(html) -> ProductRecord` — abstract.
  - Per-site rate limit (e.g., 1 req / 2s default, configurable in `config/nurseries.yaml`).
- `class ProductRecord(BaseModel)` — pydantic v2, all fields optional except identifying ones (no `"9 cm"` defaults; `None` is a first-class value and surfaced in the report).
- `class ScrapeReport`:
  - per-site counts: pages fetched, products attempted, products parsed, products dropped (and reason: missing price / missing name / parse error).
  - written to `reports/{date}.json` and to `data/scrape_reports.parquet` (history).
- `structlog` config: JSON to file (`logs/{date}.jsonl`), pretty to stdout.
- Snapshot diff check: at end of run, compare today's per-site count vs 7-day median; if Δ > ±25%, exit non-zero so CI alerts.

Hardcoded fallbacks (`return "9 cm"` etc.) are removed across all scrapers — `size` becomes properly nullable.

### 7.2 Per-scraper rewrite

Each existing scraper rewritten on top of `BaseScraper`. Order (worst first):

1. **gardens4you** — kills the global `session = HTMLSession()` module-level state, removes the `raise Exception(...)` on size parse.
2. **arboretum** — fixes the silent fallback to `"9 cm"`, replaces driver/session lifecycle with context manager.
3. **carragh** — collapses the four-deep `NoSuchElementException` chain into a single XPath OR.
4. **quickcrop** — moves to Playwright (was Selenium).
5. **tullys** — already simplest; mostly cosmetic.
6. **rhs** — the encoding band-aids in `rhs.py:19,71-89` get replaced by a proper `ftfy.fix_text()` pass. The `if "spread" in locals()` smell gone. Synonyms now captured into the new `synonyms[]` field.

Each scraper grows a `prefer_url_botanical_name()` method (per Q2 / B2) that tries to extract the structured botanical name from URL slug or a dedicated page field before falling back to the title — significantly improves matching upstream.

### 7.3 New nurseries (per Q7 + sub-project R)

Three explicit additions from Q7:

- **Farmer Gracy** (`farmer_gracy.py`) — Shopify-based, GBP. Bare-root specialist. Currency conversion to EUR via cached ECB rate.
- **Bulbi.nl** (`bulbi.py`) — bulbs and perennials. NL site, EUR. VAT may not be included for Ireland buyers — flag in nursery config.
- **GreenGardenFlowerBulbs.nl** (`greengardenflowerbulbs.py`) — bulk bulbs. NL site, EUR, no VAT, min order. Flag both in config.

**Plus:** a prioritised subset from `docs/research/nurseries-ireland-shipping.md` (sub-project R). The exact selection is made when sub-project R completes, picking the top candidates by value-reputation × Ireland-shipping-quality × low-anti-bot-risk. Targeting **5–10 additional nurseries** in the v1 push, with the remainder available as incremental adds post-MVP.

For each: probe the site once to confirm anti-bot behaviour (see §10). If Cloudflare-protected, route through a self-hosted runner. New nursery additions after the v1 push are small, well-scoped PRs against the established `BaseScraper` foundation.

### 7.4 Test fixtures

For each scraper: 1 listing-page HTML snapshot + 2 product-page HTML snapshots committed to `tests/fixtures/{site}/`, plus a smoke test using `pytest-recording`/`vcrpy` that asserts the parser produces a valid `ProductRecord` from the fixtures. When a site changes, the snapshot diff makes it obvious.

### 7.5 Success criteria

- All 8 scrapers (5 existing + 3 new) run on the new base.
- Zero hardcoded "default" values for `size`, `stock`, `price`, `description`.
- Per-run report shows non-zero rows for every site.
- Snapshot diff alerts work (verified by running with one fixture deliberately broken).

---

## 8. Sub-project 3 — Dashboard (Observable Framework)

### 8.1 Tech

- **Observable Framework** static site in `site/`.
- DuckDB-WASM loads `data/products.parquet` + `data/rhs.parquet` + `data/nurseries.parquet` (config materialized) + `data/scrape_reports.parquet` directly in the browser.
- Build deploys to GitHub Pages (`https://aburnsy.github.io/blaithin_files/`).

### 8.2 Pages / views

Per Q3 dashboard requirements (drill-down, sortable tables, embedded links):

1. **Plant search** — primary view.
   - Filter sidebar: soil type, sun exposure, hardiness, height range, foliage, RHS award only, in-stock only, plant type (Tree / Shrub / Perennial / Bulb / Grass / etc.), cultivar text search.
   - Filters drill-down: results update; subsequent filters operate on the narrowed set.
   - Result table: one row per cultivar (or species if no cultivar), columns = [name, cultivar, common name, RHS link, cheapest price + nursery, all prices (expandable), in stock?, hardiness, soil, sun].
   - Sortable by any column.
   - Each price links to the nursery product page; each plant name links to the RHS page.
2. **Cultivar detail** — one row per nursery price.
   - Columns: [nursery, price (EUR), price (native), size, stock, delivery fee, min order, VAT note, total to your door (estimated), product link].
   - Nursery names link to nursery base URL.
3. **Non-plant comparison** — separate view for compost/tools/pots/fertilisers.
   - Same drill-down + sortable pattern but filtered to `is_plant = false`.
4. **Nursery overview** — one row per nursery with delivery fee, min order, VAT note, last-scraped date, product count, price-percentile vs market.
5. **Health page** — scrape report visualization: per-site row counts over time, error counts, snapshot-diff alerts, last-successful-run timestamp.

### 8.3 UX choices

- Dark/light theme toggle (Observable native).
- URL-encoded filter state so filter combos are shareable.
- All data fetched once on page load; subsequent navigation is in-memory.

### 8.4 Success criteria

- A user can filter to "Acer palmatum cultivars, hardy to H6, full sun, in stock" and see one row per cultivar with all nursery prices, sortable by total-to-your-door.
- All RHS and product links work.
- Page loads in < 3s on a typical broadband connection (parquet bundle target ≤ 5MB compressed).

---

## 9. Sub-project 4 — Observability + tests + CI

- `.github/workflows/ci.yml`: on PR, run linters (ruff), tests (pytest with VCR fixtures), build dashboard (`npm --prefix site run build`).
- `.github/workflows/scrape.yml`: nightly cron — see §10 for runner strategy.
- `.github/workflows/deploy.yml`: on push to `main` after a successful scrape, deploy `site/dist/` to GitHub Pages.
- Failing scrapers do **not** abort the run — each scraper is its own job; the deploy reads whatever data is present + flags missing sites on the health page.
- Snapshot-diff failure = workflow exit code 1 = email notification (default GHA behaviour).

---

## 10. Hosting / orchestration & bot detection (response to Q6)

The user's concern is correct: GitHub Actions runners use Azure IP ranges that are heavily fingerprinted by Cloudflare, DataDome, PerimeterX. Running a scraper on Actions is a 50/50 against any site with serious anti-bot.

**Strategy: hybrid runner profile per nursery.**

`config/nurseries.yaml` gets a `runs_on:` field:

```yaml
tullys:
  runs_on: github-actions       # small WooCommerce / ASP.NET, no Cloudflare
arboretum:
  runs_on: github-actions
carragh:
  runs_on: github-actions
gardens4you:
  runs_on: github-actions
quickcrop:
  runs_on: github-actions       # to verify; was Selenium-only
farmer_gracy:
  runs_on: self-hosted          # Shopify + Cloudflare suspected
bulbi:
  runs_on: self-hosted          # to verify
greengardenflowerbulbs:
  runs_on: self-hosted
rhs:
  runs_on: github-actions       # charity site, gentle
```

Two runner pools available:

- **`github-actions`** — free, ephemeral, default. Use for sites that don't actively block.
- **`self-hosted`** — your local PC (or a €5/mo VPS) registered as a self-hosted GHA runner. No bot-detection issues because traffic comes from a residential/normal-looking IP. The runner only spins up when there's a job; idle cost is zero.

**Probe-first approach:** before any new site is added to `github-actions`, run it once on Actions in CI. If it returns a 403 / Cloudflare challenge, switch its profile to `self-hosted`. The runner profile change is a one-line YAML diff.

This keeps the **majority** of the system free and reproducible, while the handful of bot-blocked sites get a working path. We do not commit to paid scraping proxies (Bright Data, ScrapingBee) up-front — only revisit if self-hosted runner proves insufficient.

**Self-hosted runner setup** is a 5-minute job: `gh actions-runner register ...` on your PC. It runs as a service in the background; `actions/runner` repo has Windows installer.

---

## 11. Open questions for spec review

These are decisions I made without explicit input — flag any you want to redirect on:

1. **Repo name:** keep `blaithin_files` (simpler, no URL changes). Alternative: rename to `blaithin` and archive the sister repo.
2. **Currency display:** I propose EUR as the single comparison currency, with native price shown alongside. Acceptable, or do you want to leave native?
3. **Bulbs as plants:** `Tulipa 'Apricot Beauty'` is a plant (gnparser parses it). I propose `is_plant = true, product_category = "bulb"` so users can filter both ways.
4. **Match override editing:** I propose `data/match_overrides.parquet` is editable via a small `python scripts/edit_overrides.py` CLI that loads the parquet, lets you change rows, writes it back. Alternative: keep it as YAML for direct editing.
5. **Self-hosted runner location:** your home PC or a VPS? PC = free but needs to be on for nightly cron. VPS = €5/mo, always-on.
6. **First nursery to rewrite as the BaseScraper exemplar:** I picked `gardens4you` (worst). Want to redirect to a different one?
7. **Existing dashboard URL:** the Looker Studio dashboard at `004c1328-...` will be deprecated. Anyone else using it that needs warning?
8. **New-nursery cap for v1:** I propose 5–10 additional nurseries from sub-project R's research output, on top of the three you named. Hard cap, soft cap, or "as many as the research finds worth doing"?
9. **UK seed/bulb-only nurseries:** post-Brexit many UK nurseries only ship dormant material to IE (no live plants). Worth scraping for the things they CAN ship (often the cheapest seeds/bulbs), or skip to keep the data model simpler? I propose include with a `live_plants_to_ireland: false` flag in nursery config so the dashboard can show "seeds and bulbs only — not live plants" badges.

---

## 12. Out of scope (explicit non-goals for v1)

- Multi-language support (English only).
- User accounts / saved searches / wishlists.
- Email price-drop alerts.
- Mobile app.
- Stock notifications.
- Affiliate/referral tracking.
- Scraping non-Irish-shipping nurseries beyond the three new ones.
- Attempting to capture cultivar-level RHS data (RHS doesn't reliably publish it).

---

## 13. Implementation plan

After your approval of this spec, the next step is a detailed implementation plan written via the `superpowers:writing-plans` skill. That plan will decompose each sub-project into review-checkpoint-sized tasks with explicit success criteria, file paths, and test commands per task.
