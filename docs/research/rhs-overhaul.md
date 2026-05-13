# RHS scraper overhaul — design

Date: 2026-05-13
Status: proposed

## Goal

Replace the HTML+Selenium-based RHS scraper with an API-driven fetch that:

1. Hits the public Azure-hosted RHS plant detail JSON endpoint.
2. Writes a single `data/rhs/data.parquet` (no more one-file-per-plant).
3. Is resumable if killed mid-run.
4. Tolerates transient HTTP failures and logs unrecoverable failures to a sidecar.
5. Drops the per-plant parquets we already have (3,791 of 67,745 IDs cached today)
   in favour of re-fetching, since the new schema is wider and the API is fast.

## Findings from probing

### Detail API

Endpoint: `GET https://lwapp-uks-prod-psearch-01.azurewebsites.net/api/v1/plants/details/{id}`

- Public, no auth, no rate-limit headers seen.
- ~4-7 KB JSON per plant, ~300 ms median latency.
- Returns a 200 with full payload for valid IDs; 404 for unknown.
- Tolerated 16 concurrent workers in a 50-id probe without throttling — sustained
  ~43 req/s. Headroom is plenty; 8-12 workers is a comfortable steady state.
- At 12 workers × 67,745 IDs ≈ 25-30 minutes total wall time. Compare with the
  current scraper, which runs for hours per partial pass.

### Schema (fields the API returns)

The detail response has ~60 top-level fields. The ones that map to either the
existing `extract_detailed_plant_data()` output or the new `RhsRecord`
(src/matching/models.py) target schema:

| API field                      | Type              | Notes                                      |
| ------------------------------ | ----------------- | ------------------------------------------ |
| `id`                           | int               | -> `rhs_id`                                |
| `botanicalName`                | string (HTML)     | tags need stripping (`<em>`, `×` literal)  |
| `botanicalNameUnFormatted`     | string            | plain text — preferred                     |
| `commonName`                   | string            | legacy display name                        |
| `commonNames`                  | list[str]         | -> `common_names`                          |
| `synonyms`                     | list[{id,name}]   | name has `<em>` tags, strip & keep strings |
| `family`                       | string            |                                            |
| `genus`                        | string            |                                            |
| `isAgm`                        | bool              | -> `is_rhs_award_winner`                   |
| `isPlantsForPollinators`       | bool              | -> `is_pollinator_plant`                   |
| `height`                       | string            | already a human range, e.g. "1.5-2.5 metres"|
| `spread`                       | string            | same                                       |
| `timeToFullHeight`             | list[int]         | enum, not currently used downstream        |
| `sunlight`                     | list[int]         | decode via bundle map                      |
| `soilType`                     | list[int]         | decode -> `soils`                          |
| `moisture`                     | list[int]         | decode (singular string in RhsRecord)      |
| `ph`                           | list[int]         | decode -> list of strings                  |
| `aspect`                       | list[int]         | decode                                     |
| `exposure`                     | list[int]         | decode                                     |
| `plantType`                    | list[int]         | decode using existing `plant_type_mapping` |
| `foliage`                      | list[int]         | decode                                     |
| `habit`                        | list[int]         | decode                                     |
| `hardinessLevel`               | int               | decode to "H1A".."H7" string               |
| `entityDescription`            | string            | -> `description`                           |
| `plantEntityId` / URL synthesis| —                 | rebuild `plant_url` from id + botanical    |

Fields we drop (not currently consumed downstream and not in RhsRecord):
`autoCompleteField*`, `colourWithAttributes`, `cultivation`, `pruning`,
`propagation`, `pestResistance`, `diseaseResistance`, `toxicity`, `fragrance`,
`notedForFragrance`, `nurseriesCount`, `range`, `seasonColourAgg`,
`seasonOfInterest`, `semanticSearchField`, `suggestedPlantUses`,
`plantingPlaces`, `images`, `imageCopyRight`, `supplierURL`, `price`,
`hasFullProfile`, `isGenus`, `isSpecie`, `isSynonym`, `synonymParentPlantId`,
`synonymParentPlantName`, `nameStatus`, `genusDescription`,
`hortGroupDescription`, `heightType`, `spreadType`, `plantEntityId`.

If matching ever wants any of those, we can add them later — re-running the
scraper is cheap.

### Enum decode tables

All enum maps live in the public Angular bundle at
`https://www.rhs.org.uk/wwwroot/js/bundles/main.bundle.js`. Extracted once and
hardcoded as Python constants (small risk of drift, but they change rarely and
re-extraction takes minutes):

- sunlight: 0=No preference, 1=Full sun, 2=Partial shade, 3=Full shade
- soilType: 0=No preference, 1=Loam, 2=Chalk, 3=Sand, 4=Clay
- aspect: 0=No preference, 1=East-facing, 2=North-facing, 3=South-facing,
  4=West-facing
- moisture: 0=No preference, 1=Well-drained, 2=Poorly drained, 3=Moist but
  well-drained
- ph: 0=No preference, 1=Acid, 2=Alkaline, 3=Neutral
- exposure: 0=No preference, 1=Sheltered, 2=Exposed
- foliage: 0=No preference, 1=Deciduous, 2=Evergreen, 3=Semi evergreen
- habit: 0=No preference, 1=Bushy, 2=Climbing, 3=Clump-forming,
  4=Columnar/upright, 5=Floating, 6=Mat-forming, 7=Pendulous/weeping,
  8=Spreading branched, 9=Submerged, 10=Suckering, 11=Trailing, 12=Tufted
- hardinessLevel: 0=Unknown, 1=H1A, 2=H1B, 3=H1C, 4=H2, 5=H3, 6=H4/H5
  (collision in bundle — same int for both), 7=H6, 8=H7
- plantType: already mapped in `src/scrapers/rhs_urls.py` —
  `plant_type_mapping`; move to a shared `src/scrapers/rhs_enums.py`

## Storage strategy

### Options considered

**A. JSONL staging → parquet finalise.**
Append a JSON line per fetched ID to `data/rhs/_staging.jsonl`. Resume: read the
file once, build a set of seen IDs, skip them. At end of run, read JSONL into
polars and write `data.parquet`. Simple. No mid-run parquet queryability.

**B. PyArrow dataset writes (row-group append).**
Use `pyarrow.dataset.write_dataset` with `partitioning=None`,
`existing_data_behavior="overwrite_or_ignore"`. Mid-run the dataset directory
is queryable. Schema-evolution edge cases under partial writes are sharp.

**C. SQLite staging → parquet finalise.**
Open `data/rhs/_staging.sqlite`, single table `plants(id INTEGER PRIMARY KEY,
fetched_at TEXT, raw_json TEXT, ...decoded columns...)`. Each successful fetch
is an `INSERT OR REPLACE` inside a transaction. Resume: `SELECT id FROM plants`
gives the seen set. At end of run, dump to parquet and (optionally) keep the
sqlite around for forensics. Mid-run the data is fully queryable via the
sqlite CLI.

**D. Single parquet rewritten every N rows.**
At 67,745 rows and any modest N, write-amplification dominates. Rejected.

### Recommendation: **C — SQLite staging**

Why:
- Stdlib only (Python ships `sqlite3`).
- Resume is a one-liner: `SELECT id FROM plants` — fast even at 67k rows.
- Atomic inserts, so kill-9 at any moment leaves a clean DB and at most one
  in-flight fetch's worth of lost work.
- Easy ad-hoc forensic queries during a long run ("how many failures so far",
  "show me what we got for id=98658").
- We can stash the raw JSON in a TEXT column. Re-parsing without re-fetching
  becomes free — useful if we discover a new enum field or fix a parser bug.
- Finalising to parquet is one polars step at the end.

Alternative (B) is appealing for the mid-run parquet queryability, but the
crash semantics of partial dataset writes are murky and the pyarrow API for
incremental row-group append is awkward. (A) is the simplest fallback if
SQLite proves friction-y; behaviour is otherwise identical.

The sqlite file is kept on disk after the run as a forensic artefact, not
checked into git. `.gitignore` already covers `data/rhs/*` via the existing
parquet-pattern ignore — add `data/rhs/_staging.sqlite*` explicitly.

## Concurrency

- `concurrent.futures.ThreadPoolExecutor`, `max_workers=12`.
- The existing `src.scrapers.http.fetch_html` is sync (httpx + tenacity). Reuse
  the retry logic but call it from worker threads. No need to bring in asyncio
  for a one-off batch.
- Per-request: `httpx.Client` shared across threads (httpx clients are thread-
  safe for sync use). 30s timeout. 3 retries with exponential backoff.
- Treat HTTP 404 as **terminal not-found**, not a retryable error — record the
  ID in the failed-ids sidecar and move on.
- Rate limit: none by default. If we observe 429s, drop concurrency first, add
  a token bucket only as a last resort.

## Failure handling

- Successful fetch -> row in `plants` table.
- 404 -> row in `failed_ids(id INTEGER PRIMARY KEY, reason TEXT, attempts INT)`.
- 5xx / network / timeout -> retried up to 3x; on final failure, row in
  `failed_ids` with reason set to the exception type.
- A `--retry-failed` flag re-tries everything in `failed_ids` (clearing the
  row on success). Useful for "the API was flaky during last night's run".

## Resumability

On startup, the scraper:

1. Opens `data/rhs/_staging.sqlite` (creating if missing).
2. Reads `SELECT id FROM plants` into a Python set.
3. Reads the input ID list from `data/rhs_urls.parquet`.
4. Computes `to_fetch = input_ids - seen_ids - permanent_404s`.
5. Streams `to_fetch` into the worker pool.

A run killed at 30,000 / 67,745 picks up the next time with the remaining
~37,745 IDs and the same threadpool. No special "resume mode" flag — resume is
the default behaviour.

## Final parquet write

After the fetch loop exits cleanly:

1. `SELECT decoded columns FROM plants` via polars `read_database`.
2. Cast to the RhsRecord-aligned schema (List[str] for synonyms / plant_type /
   common_names etc.; nullable strings for height/spread/moisture/hardiness;
   bool for is_rhs_award_winner / is_pollinator_plant).
3. `df.write_parquet("data/rhs/data.parquet")`.

Freshness gate (`src/common/freshness.py`) already keys off
`data/<source>/data.parquet` mtime, so this lands in the right place.

## Schema produced (parquet columns)

Aligned with `src/matching/models.py:RhsRecord`. Final column set:

```
rhs_id              int64
plant_url           str
botanical_name      str        # botanicalNameUnFormatted, stripped
genus               str
species             str        # parsed from botanical_name (existing helper)
family              str | null
common_name         str | null # singular — legacy fuzzy matcher reads this
common_names        list[str]  # plural — RhsRecord target
synonyms            list[str]  # names only, HTML-stripped
plant_type          list[str]
description         str | null
is_rhs_award_winner bool
is_pollinator_plant bool
height              str | null
spread              str | null
soils               list[str]
moisture            str | null
ph                  list[str]
sun_exposure        list[str]
aspect              list[str]
exposure            list[str]
hardiness           str | null
foliage             list[str]  # was singular str | null in old scraper bug
habit               list[str]
source              str        # always "rhs"
```

Two notes on schema choices:

- **Both `common_name` and `common_names`.** The legacy
  `src/matching/fuzzy.py` and `src/matching/exact.py` still read `common_name`
  (singular). `RhsRecord` declares `common_names: list[str]`. Producing both
  costs almost nothing and means the new parquet is a drop-in replacement for
  the legacy `data/rhs.parquet` AND aligned with the target model. When
  matching migrates fully to the new shape, the singular column gets deleted.
- **`foliage` is a list, not a string.** The API returns a list; the old
  scraper sometimes returned a list and sometimes None. List is correct.

## Migration of the 3,791 cached parquets

**Decision: re-fetch, don't migrate.**

Rationale: the API can re-fetch all 3,791 in ~90 seconds at 12 workers. The
new schema is wider and partially decoded differently than the old one;
migrating would mean writing schema-mapping code that nobody will ever look at
again. The fetched data is identical to what re-running would produce.

The per-plant `data/rhs/*.parquet` files get deleted as the first step of the
new scraper (after a one-line confirmation in the logs). This also avoids the
risk of leaving stale per-plant files alongside the new aggregate.

## File layout

```
src/scrapers/
  rhs.py              # rewritten — see below
  rhs_enums.py        # NEW — frozen enum decode tables + plant_type_mapping
  rhs_urls.py         # unchanged behaviour; imports plant_type_mapping from rhs_enums

data/rhs/
  data.parquet        # final output (one file, 67k rows)
  _staging.sqlite     # forensic; not committed
  failed_ids.txt      # NEW — newline-delimited IDs we gave up on
```

## Module shape

`src/scrapers/rhs.py` becomes:

- `STAGING_DB = data/rhs/_staging.sqlite`
- `FINAL_PARQUET = data/rhs/data.parquet`
- `_init_db(conn)` — creates tables if absent.
- `_seen_ids(conn)` -> set[int]
- `_failed_ids(conn)` -> set[int]
- `parse_detail(payload: dict) -> dict` — pure, the testable core. Takes the
  raw API response, returns the column dict.
- `_fetch_one(client, id) -> dict | None` — fetches via shared httpx client,
  uses `src.scrapers.http` retry logic, returns parsed row or raises a typed
  `Fetch404` / `FetchFailed`.
- `_worker(id, ...)` — calls `_fetch_one`, writes to sqlite under a lock.
- `get_plants_detail(plants)` — the entry point called from load_bronze_data.
  Sets up the pool, drives the loop, finalises the parquet.
- `--retry-failed` exposed via a CLI flag handled in load_bronze_data.

`load_bronze_data.py` change: the `case "rhs":` branch becomes a single call
to `rhs.get_plants_detail(...)`. Drop the post-merge step that used
`scan_pyarrow_dataset(ds.dataset("data/rhs/"))` because the scraper now writes
the final parquet itself.

Also update `_run_matching` to read `data/rhs/data.parquet` instead of
`data/rhs.parquet`.

## Tests

- `tests/scrapers/test_rhs_parse.py` — fixture-based: feed a small JSON
  payload (use the real Forsythia response saved as a fixture, plus the
  Phalaenopsis one with missing hardinessLevel and the Delphinium one which
  is a synonym) through `parse_detail()` and assert the column dict.
- `tests/scrapers/test_rhs_enums.py` — every enum decode table covers the
  whole 0..N range without KeyError.
- `tests/scrapers/test_rhs_resume.py` — write three fake rows to a tmp sqlite,
  call `_seen_ids()`, assert the right set comes back.

No end-to-end "hits the real API" test in the unit suite — keep that out of
the offline-friendly suite and run it ad-hoc.

## Out of scope

- Decoding `cultivation` / `pruning` / `propagation` HTML into structured data.
- The colour-and-scent matrix the old scraper parsed and then commented out.
- Image URL handling (`images[]`) — nothing downstream uses them.
- Refactoring `src/matching/fuzzy.py` to use `common_names` plural — that's a
  follow-up; the new parquet emits both forms so neither version of the
  matcher is broken.

## Risks

- **Enum table drift.** If RHS reshuffles the int values for an enum in their
  Angular bundle, the decoded strings go wrong silently. Mitigation: keep the
  raw JSON in sqlite so we can re-decode without re-fetching, and add a smoke
  test that re-extracts a single ID's full payload and diffs against the
  fixture (manual, not in CI since there is no CI).
- **API disappears or changes URL.** The endpoint is on an Azure App Service
  domain owned by a third-party (looks like a contractor). If it goes away,
  we fall back to HTML scraping or a different data source. The matching
  pipeline degrades gracefully (RHS rows just stop refreshing); nothing
  collapses.
- **404 noise.** `data/rhs_urls.parquet` was built from the search API and may
  not be in perfect sync with the detail API. Expect some 404s. Logged to
  `failed_ids.txt` and ignored.
