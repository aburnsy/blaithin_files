# blaithin_files

Plant price comparison across Irish, UK, and EU online nurseries.

## What this is

Daily scrapes of nursery websites → matched to RHS plant database →
fed into a local Streamlit wishlist optimiser that finds the cheapest
nursery-subset plan to door for a list of desired plants.

- **Spec:** `docs/superpowers/specs/2026-05-13-wishlist-optimiser-design.md`
- **Plans:** `docs/superpowers/plans/`
- **Nursery research:** `docs/research/nurseries-ireland-shipping.md`

## Run locally

```
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
python load_bronze_data.py --site tullys         # scrape one site
python load_bronze_data.py --matching            # run matching + size normalisation
streamlit run scripts/wishlist.py                # launch the optimiser
```

## Scrape cadence

Re-runs skip any site whose newest `data/<source>/<date>.parquet` is less
than 30 days old. Nursery pricing and stock change seasonally, not daily,
so a monthly refresh is enough and a same-day re-dispatch only retries the
sites that have no fresh parquet.

Knobs:

- `SCRAPE_MAX_AGE_DAYS` (env, default `30`) — change the freshness window.
- `FORCE_SCRAPE=1` (env), `--force` (CLI), or the `force` `workflow_dispatch`
  input — bypass the gate entirely.

Local example:

```
FORCE_SCRAPE=1 python load_bronze_data.py --site tullys     # bash
$env:FORCE_SCRAPE=1; python load_bronze_data.py --site tullys  # PowerShell
```

See: `docs/superpowers/specs/2026-05-12-scrape-freshness-gate-design.md`

## Layout

- `src/scrapers/` — site-specific scrapers, all on `BaseScraper`
- `src/matching/` — gnparser+rapidfuzz+LLM-fallback pipeline
- `src/transforms/` — post-matching transforms (e.g., size normalisation)
- `src/wishlist/` — wishlist optimiser core (pure Python)
- `src/common/` — storage, logging, FX, nursery config loader
- `scripts/wishlist.py` — Streamlit app entry point
- `data/` — parquet snapshots (committed; refreshed by monthly cron)
- `config/` — per-nursery URL lists + `nurseries.yaml` metadata
- `tests/` — pytest suite + VCR fixtures
