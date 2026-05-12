# Scrape freshness gate — design

**Date:** 2026-05-12
**Status:** Approved (proceeding to implementation)

## Problem

Re-running the nightly scrape workflow (manual dispatch, or any second run on
the same day) currently re-scrapes every site from scratch. This wastes
compute on sites that already have fresh data, and re-wastes it on sites that
succeeded earlier in the same day. Nursery pricing/availability changes
seasonally, not daily, so a ~30-day cadence is sufficient.

## Goals

1. **Throttle.** Skip a site if `data/<source>/` already contains a parquet
   less than `SCRAPE_MAX_AGE_DAYS` (default 30) old.
2. **Failure retargeting.** A re-run on the same day attempts only sites that
   don't already have today's parquet. Falls out of goal 1 automatically: a
   successful site has age 0 < 30 → skipped; a failed site has no fresh
   parquet → runs.
3. **Force override.** An explicit knob bypasses both behaviours for ad-hoc
   full re-scrapes. Works in CI (`workflow_dispatch` input) and locally
   (env var or CLI flag).

## Non-goals

- Scraper internals (tullys / quickcrop / carragh / arboretum were just
  fixed; do not touch).
- The match-and-commit job's commit logic.
- Per-site cadence overrides — global default for now; structure leaves room
  for it later.
- Dashboard or matching pipeline changes.

## Design

### Where the gate lives

In Python, as a single function in a new module `src/common/freshness.py`:

```python
def should_scrape(
    source: str,
    *,
    max_age_days: int = 30,
    force: bool = False,
    today: datetime.date | None = None,
    data_root: Path = Path("data"),
) -> tuple[bool, str]:
    """Return (run, reason). reason is a one-line log message."""
```

`load_bronze_data.py:main` calls it before each scraper dispatch. If
`run is False`, log the reason and return without scraping.

**Why Python, not YAML:** local runs benefit automatically, the logic is
unit-testable, and there's a single source of truth. The Actions UI loses its
"skipped" badge, but a structured log line at the top of the job
(`SKIP <source>: fresh parquet 2026-05-02 (age 10d)`) is just as findable.

### Freshness rule

A source is **fresh** (skip) iff:

1. `data/<source>/` exists and contains at least one `*.parquet`, AND
2. the newest parquet (lexicographic sort works — names are `YYYY-MM-DD.parquet`)
   is readable, AND
3. that parquet has `num_rows >= 1` (cheap via `pq.ParquetFile(path).metadata.num_rows`), AND
4. `today - file_date < max_age_days` (parsed from filename stem).

Any other state — no directory, no parquet, unreadable, 0 rows, malformed
filename, or too old — is **stale**. Scrape.

`force=True` skips all checks and returns `(True, "FORCE: bypassing freshness gate")`.

### Knobs

| Knob | Where | Default | Notes |
|------|-------|---------|-------|
| `SCRAPE_MAX_AGE_DAYS` | env | `30` | Cast to int; non-int → fall back to 30 + warn. |
| `FORCE_SCRAPE` | env | unset | Truthy values: `1`, `true`, `yes` (case-insensitive). |
| `--force` | CLI flag on `load_bronze_data.py` | off | Mirrors `FORCE_SCRAPE`. Either one being set wins. |
| `force` | `workflow_dispatch.inputs` (boolean) | `false` | Wired into `env: FORCE_SCRAPE: ${{ inputs.force }}` on the scrape job. |

### How the two behaviours compose

The 30-day throttle subsumes "retry-only-failures" automatically:

- **First dispatch of the day**, site succeeded yesterday → newest parquet is
  yesterday's, age 1 < 30 → skip.
- **Re-dispatch later same day**, site succeeded earlier → today's parquet
  exists, age 0 < 30 → skip.
- **Re-dispatch later same day**, site failed earlier → no today parquet;
  newest is older than 30 days (or doesn't exist) → run. If newest is from
  last week (<30 days), we still skip — this matches goal 1's intent. The
  user accepts this: failed scrapes within the 30-day window will wait for
  the next "real" stale window unless `force=true`.

  > **Note:** This means a transient failure inside the 30-day window is not
  > auto-retried by a same-day re-dispatch. Use `force=true` to retry. This
  > is intentional — explicit, not silent.

### Workflow changes

Keep the existing 7-way matrix. Add `workflow_dispatch.inputs.force`:

```yaml
on:
  schedule:
    - cron: "0 4 * * *"
  workflow_dispatch:
    inputs:
      force:
        description: "Force full re-scrape, ignoring freshness gate"
        type: boolean
        default: false
```

And expose it as env on the scrape job:

```yaml
jobs:
  scrape:
    env:
      FORCE_SCRAPE: ${{ inputs.force }}
```

(For the cron-triggered case, `inputs.force` is the empty string → falsy → throttle active. This is correct: the nightly cron should honour throttling.)

Artifact upload (`if-no-files-found: error`) is safe: skipped sites still
have their existing `data/<source>/` directory to upload, and a never-scraped
site can't be "fresh" (no parquet → stale → runs).

### Match-and-commit behaviour

No changes. `_run_matching` already does `parquets[-1]` per nursery — a
missing today-file transparently falls back to the most recent prior file.
Confirmed by reading `load_bronze_data.py:_run_matching` at lines 25–50.

## Files touched

- **New:** `src/common/freshness.py` — `should_scrape()` function.
- **New:** `tests/common/test_freshness.py` — unit tests using `tmp_path`.
- **Modified:** `load_bronze_data.py` — call gate before each scraper case;
  add `--force` flag.
- **Modified:** `.github/workflows/scrape.yml` — add `force` input + env wiring.
- **Modified:** `README.md` — add "Scrape cadence" section.

## Test plan

`tests/common/test_freshness.py` covers (with `tmp_path` for `data_root`):

1. No `data/<source>/` directory → stale.
2. Empty `data/<source>/` directory → stale.
3. Parquet exists, today, ≥1 row → fresh.
4. Parquet exists, 10 days old, ≥1 row → fresh.
5. Parquet exists, 31 days old, ≥1 row → stale.
6. Parquet exists, today, 0 rows → stale.
7. Custom `max_age_days=7`, parquet 8 days old → stale.
8. `force=True` overrides every fresh case → returns `(True, "FORCE: ...")`.
9. Malformed filename (`not-a-date.parquet`) → stale (treat as unparseable).
10. Multiple parquets present — newest one wins.

## Done criteria

- First manual dispatch on a fresh day: sites <30d old log `SKIP` and exit
  fast; older sites scrape normally.
- Second manual dispatch same day: only sites without today's parquet (and
  no fresh-enough prior parquet) run.
- `force=true` workflow input runs everything.
- `python load_bronze_data.py --site tullys` respects throttle; `--force`
  bypasses it.
- README "Scrape cadence" section explains the behaviour.
- `pytest tests/common/test_freshness.py` passes.
