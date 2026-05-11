# Blaithin redesign — decisions needed

Pick an option per question (or write your own). One-line answer is fine. The recommended option is marked with a star and a short reason; you can just write "recommended" or the letter. If you have a different idea, just describe it.

---

## Q1. Scraping approach

How much do we change the scraping layer?

- **A1.** Full rewrite onto **Scrapy** framework. Free retries / throttling / pipelines, but big migration for 5 sites and JS sites still need `scrapy-playwright`.
- **A2.** ⭐ **Thin `BaseScraper` + standard libs** (`tenacity` retries, `structlog` logging, `pydantic` models, context-managed drivers, kill hardcoded fallbacks). Keep per-site files, just stop the bleeding. *Recommended — smallest blast radius, biggest reliability win per hour spent.*
- **A3.** Full **Playwright + httpx** rewrite. One stack across all scrapers (replaces both Selenium and `requests-html`). Cleaner than A2 long-term, more upfront work.

**Your answer:**

> Some sites are ok with static. Others require selenium. THe crux of the issue is that some sites are good at stopping scraping. I need to be more robust. I will go with your recommendation.

**Notes / variations:**

> 

---

## Q2. RHS matching approach

The current matcher (`match_product_to_plant.py:36-98`) flattens cultivar away — "Acer palmatum 'Bloodgood'" matches the plain "Acer palmatum" RHS row, and every cultivar from every nursery collapses onto the same record. Fix needs both a better matcher *and* a data-model change so cultivar survives.

Pick a matching strategy:

- **B1.** **`gnparser` only** — Global Names Parser parses botanical strings into genus/species/cultivar deterministically. Free, fast, but doesn't handle nursery cruft like "9cm" or pot codes — needs a pre-clean step.
- **B2.** **URL/HTML scraping** for the structured name where nurseries already expose it as a separate field. Most reliable signal but site-specific work per scraper.
- **B3.** ⭐ **Two-stage: deterministic (B1+B2) + LLM batch fallback** for the unmatched residual. Cache results in `data/match_overrides.parquet`, only re-run on deltas. *Recommended — cheap (pennies per delta with prompt caching), correct on the long tail (synonyms, common-name-only, misspellings), human-auditable cache.*
- **B4.** **Hand-curated alias YAML** + token match. Full control, doesn't scale, you become the bottleneck.

Plus the **data-model rework** (regardless of which matcher): one RHS row per (genus, species) with a `synonyms[]` field — currently `rhs.py:34` actively discards synonyms — and cultivar lives on the *product* row. RHS rarely has per-cultivar pages, so this is the right shape.

**Your answer (matching strategy):**

> B3 - One thing we're poor on today is flagging where products are Not plant related e.g. tools etc. We should also consider this. A nice-to-have would be to categorise those e.g. Soil, compost, tools etc so that we can even compare those prices

**Your answer (data-model rework — yes / no / different):**

> yes sure

---

## Q3. Dashboard / hosting approach

Single repo, free static hosting (replaces Looker Studio + BigQuery + GCS).

- **C1.** ⭐ **Observable Framework** — static-site generator from the D3 author, purpose-built for data dashboards. Loads parquet via DuckDB-WASM in browser, filters in SQL client-side, deploys to GitHub Pages. *Recommended — designed for exactly this, minimal frontend code.*
- **C2.** **React/Svelte SPA + DuckDB-WASM** — hand-rolled. Full design control, ~3-4× the code for the same outcome.
- **C3.** **Static JSON + vanilla JS** filtering. Simplest, but doesn't scale past ~10k rows; no SQL.

**Your answer:**

> C1

**Notes (any specific dashboard features you want / hate about Looker Studio):**

> I want to be able to drill down. Select soil type, then Sun amount etc. I want to be able to order tables by whatever metric I choose. I would like links embedded - both to the rhs and the various sites that sell the products.

---

## Q4. Decomposition order

Five sub-projects: 0 = repo consolidation, 1 = scraping hardening, 2 = matching v2, 3 = dashboard, 4 = observability/tests.

- **D1.** **0 → 1 → 2 → 3 → 4** (linear, scraping cleanup first, my original instinct).
- **D2.** ⭐ **0 → 2 → 1 → 3 → 4** (matching first, because it defines the data shape the dashboard consumes — building dashboard against wrong schema means rework). *Recommended.*
- **D3.** **0 first, then 1/2/3 in parallel** (if you ever want to dispatch to separate work streams or run agents in parallel; 4 last).

**Your answer:**

> D2

---

## Q5. LLM use for matching

- **L1.** ⭐ **Anthropic Haiku 4.5 with prompt caching** — cheap (pennies per delta), fast, uses your existing API. *Recommended.*
- **L2.** **No LLM** — fully deterministic; accept some unmatched residual that lives in a "needs review" bucket.
- **L3.** **LLM but a different model / provider** (specify).

**Your answer:**

> L1

---

## Q6. Drop Mage AI orchestration?

Currently `blaithin/docker/` runs Mage AI in Docker for orchestration. For 5 scrapers + a daily build, GitHub Actions does it in ~30 lines of YAML and is free. Mage adds a UI but also the only Docker dependency.

- **M1.** ⭐ **Drop Mage, use GitHub Actions** for daily scrape → build → deploy.
- **M2.** **Keep Mage** — you actively use the UI / find the visual pipeline editor valuable.
- **M3.** **Other orchestrator** (Prefect, Dagster, plain cron+systemd, etc.).

**Your answer:**

> M1 -> re Github actions, wouldn't we need to ensure all of these work withing a VPC or something frst? I had issues proving I wasn't a bot previosly

---

## Q7. Free-form

Anything I missed? New nursery sites you want to add? Fields you wish you had on the dashboard? Things the current setup does badly that I haven't called out? Hard constraints (deadline, cost ceiling, has-to-run-on-Windows, etc.)?

**Your answer:**

> Could you find other major nursery sites in ireland that do home deliveries for normal gardens? https://www.farmergracy.co.uk/ deliver to Ireland and they're especially cheap for bare root. Obviously ensure you include a ref to delivery fees or min orders somewhere in the site. Do same for all existing sites. https://www.bulbi.nl/en for bulbs and perrenials. https://www.greengardenflowerbulbs.nl/en for bulk orders of bulbs and perrenials - please note the lack of VAT and delivery fees on these + min order -> would need to be noted.

---

## Once you've answered

Save the file. I'll pick it up, write a design doc to `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md`, commit it, you review, then we move into implementation planning.
