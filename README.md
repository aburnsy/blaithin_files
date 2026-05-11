# blaithin_files

Plant price comparison across Irish, UK, and EU online nurseries.

## What this is

Daily scrapes of nursery websites → matched to RHS plant database →
served as a static dashboard. All free, all open.

- **Dashboard:** https://aburnsy.github.io/blaithin_files/ (GitHub Pages)
- **Spec:** `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md`
- **Plans:** `docs/superpowers/plans/`
- **Nursery research:** `docs/research/nurseries-ireland-shipping.md`

## Run locally

```
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
python load_bronze_data.py --site tullys     # scrape one site
python load_bronze_data.py --matching        # run matching pipeline
cd site && npm install && npm run dev        # run dashboard locally
```

## Layout

- `src/scrapers/` — site-specific scrapers, all on `BaseScraper`
- `src/matching/` — gnparser+rapidfuzz+LLM-fallback pipeline
- `src/common/` — storage, logging, FX, nursery config loader
- `site/` — Observable Framework dashboard
- `data/` — parquet snapshots (committed; refreshed by nightly cron)
- `config/` — per-nursery URL lists + `nurseries.yaml` metadata
- `tests/` — pytest suite + VCR fixtures
