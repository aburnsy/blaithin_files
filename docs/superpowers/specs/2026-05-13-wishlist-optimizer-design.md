# Wishlist Optimizer — Design Spec

**Status:** Approved for implementation
**Date:** 2026-05-13
**Owner:** Andrew Burns

---

## 1. Problem statement

Given a list of desired plants (with quantities, optional size constraints, and optional bare-root tolerance), find the combination of nurseries that minimises total cost to door, factoring in per-nursery shipping rules, minimum-order thresholds, and VAT differences. Today there is no way to compose a multi-plant order across the scraped nurseries; the existing Cultivar Detail dashboard page handles only one plant at a time and uses a simplistic flat-fee shipping approximation.

Secondary requirement: do this locally, with state that survives navigation and app restarts. The existing public Observable dashboard is being retired in favour of a single local Streamlit tool.

---

## 2. Goals

- Compose a wishlist of plants by selectable identity (cultivar / species / genus / category) with per-row qty, min litres, and allow-bare-root toggle.
- Persistence: wishlist survives tab switching, page interactions, and app restarts.
- Optimiser ranks all feasible nursery-subset plans by total cost to door (EUR).
- User picks a max-nursery cap via slider; UI shows the cheapest plan at that cap plus a trade-off curve for caps 1..8.
- Per-nursery basket cards show items, sizes, qty, unit/line totals, VAT note, shipping calc, deep-links to product pages.
- Surfaces unfulfilled wishlist rows with a one-click "expand cap to fit it" affordance.

## 3. Non-goals

- No public/hosted dashboard. Local single-user tool only.
- No partial fulfilment within a wishlist row ("buy 2 here, 1 there for the same row").
- No save/version history of past plans (re-run on the same data is deterministic; CSV export is the artefact).
- No multiple named wishlists in MVP (single active `.wishlist.json`).
- No MILP / globally-optimal solver. Bounded brute-force on subset enumeration is the algorithm.
- No accounting for delivery time, seasonality, in-store-only flags.
- No retention of the existing Observable Framework dashboard — it is deleted as part of this work.

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Existing Python pipeline (unchanged)                            │
│   src/scrapers/*  → src/matching/run.py → data/products_matched │
│                                                                 │
│ NEW pipeline step: src/transforms/size_normalize.py             │
│   reads data/products_matched.parquet                           │
│   adds two columns: pot_size_litres (Float|null), size_kind     │
│   writes back to data/products_matched.parquet                  │
│   runs at the end of load_bronze_data.py --matching             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ NEW local Streamlit app — `streamlit run scripts/wishlist.py`   │
│                                                                 │
│   src/wishlist/                                                 │
│     __init__.py                                                 │
│     models.py        — WishlistRow, PlantSelector, Plan, Basket │
│     sizes.py         — cm↔L lookup, fits_constraint() predicate │
│     candidates.py    — per-row candidate products from parquet  │
│                        + autocomplete option list construction  │
│     optimizer.py     — subset enumeration + plan assembly       │
│     shipping.py      — compute(basket_eur, nursery_cfg) → EUR   │
│     fx.py            — native → EUR via data/fx.parquet         │
│     state.py         — load/save Wishlist to .wishlist.json     │
│                                                                 │
│   scripts/wishlist.py   — Streamlit entry; Build/Browse/Plans   │
│   tests/wishlist/       — pytest unit tests + fixtures          │
│                                                                 │
│   Reads:  data/products_matched.parquet                         │
│           config/nurseries.yaml                                 │
│           data/fx.parquet                                       │
│   Writes: .wishlist.json   (gitignored, project-root)           │
│                                                                 │
│ REMOVED: site/  +  .github/workflows/deploy.yml (if present)    │
│          + README references to GitHub Pages dashboard          │
└─────────────────────────────────────────────────────────────────┘
```

- Compute lives entirely in Python; no JS, no backend.
- The Streamlit app is single-user, locally launched, no auth, no server-deploy story.
- Cleanup of `site/` and any GitHub Pages workflow is part of this work. Disabling GitHub Pages in the repo settings UI is a user manual step (out of scope for code).

---

## 5. Data model — size normalisation

### 5.1 New columns on `data/products_matched.parquet`

| column | type | example values |
|---|---|---|
| `pot_size_litres` | `Float64` (nullable) | `2.0`, `0.5`, `null` |
| `size_kind` | `String` (enum-like) | `potted` / `bare_root` / `rootball` / `unknown` / `non_plant` |

### 5.2 Parser logic (`src/transforms/size_normalize.py`)

Operates over each row's `size` string + `is_plant` flag. Pipeline:

```
1. If is_plant=false                                  → non_plant, litres=null
2. Match /bare\s*root/i                               → bare_root, litres=null
3. Match /rootball/i                                  → rootball,  litres=null
4. Match /(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*(L|Lit)/i   → potted,    litres=lower_bound
5. Match /(\d+\.?\d*)\s*(L|Lit)/i                     → potted,    litres=value
6. Match /P(\d+\.?\d*)/                               → potted,    litres=CM_TO_LITRES[POT_CODE_TO_CM[code]]
7. Match /(\d+(?:\.\d+)?)\s*cm/i                      → potted,    litres=CM_TO_LITRES[round(cm)]
8. else                                               → unknown,   litres=null
```

`CM_TO_LITRES` is the single source of truth for diameter → volume. P-codes funnel through `POT_CODE_TO_CM` first, then through `CM_TO_LITRES`, so the same physical pot always returns the same litre value regardless of which label the nursery used.

Range handling (step 4): take the lower bound. `10-15 Litre` → `10.0`. Conservative — never overstates a product's size.

Half-cm values (e.g. `9.5cm`) round half-up to integer cm before lookup. cm values outside 7–50 fall back to `unknown` (almost always parse noise).

### 5.3 cm → L dense lookup, 7–50cm

In `src/wishlist/sizes.py` as `CM_TO_LITRES: dict[int, int]`:

| cm | L | cm | L | cm | L | cm | L | cm | L |
|---|---|---|---|---|---|---|---|---|---|
|  7 | 0 | 16 | 2 | 25 |10 | 34 |20 | 43 |40 |
|  8 | 0 | 17 | 2 | 26 |11 | 35 |21 | 44 |43 |
|  9 | 1 | 18 | 3 | 27 |12 | 36 |23 | 45 |46 |
| 10 | 1 | 19 | 3 | 28 |13 | 37 |25 | 46 |49 |
| 11 | 1 | 20 | 4 | 29 |14 | 38 |27 | 47 |52 |
| 12 | 1 | 21 | 5 | 30 |15 | 39 |30 | 48 |55 |
| 13 | 1 | 22 | 5 | 31 |16 | 40 |32 | 49 |59 |
| 14 | 2 | 23 | 7 | 32 |17 | 41 |35 | 50 |63 |
| 15 | 2 | 24 | 8 | 33 |18 | 42 |37 |    |   |

Derived from `V ≈ 0.5 × (d/10)³` then snapped to the existing pot-code anchors from `blaithin/.../stg_products.sql` (P11=1L, P15=3L, P18=5L, P25=10L, P30=15L). Tiny pots (7–8cm) round to 0L; they fail any positive `min_litres` constraint, which matches intent.

### 5.4 Pot-code → cm lookup

In `src/wishlist/sizes.py` as `POT_CODE_TO_CM: dict[str, int]`:

```
P8.5 → 8    P9  → 9    P9.5 → 9    P10 → 10   P11 → 11
P12  → 12   P13 → 13   P14  → 14   P15 → 15   P16 → 16
P17  → 17   P18 → 18   P19  → 19   P20 → 20   P25 → 25   P30 → 30
```

Pot codes outside this set fall through to `unknown`. P-codes resolve through `CM_TO_LITRES` after this lookup — they never have an independent L value, which guarantees the same diameter always maps to the same volume regardless of input format.

Note: this differs from the historical `stg_products.sql` mapping in `blaithin/.../stg_products.sql`, where some P-codes (notably P12, P15, P18, P20) had more generous L values than the geometric estimate. The new mapping favours internal consistency over matching the old industry table; the user has accepted approximation.

### 5.5 `fits_constraint(product, row)` predicate

In `src/wishlist/sizes.py`:

```python
def fits_constraint(product: Product, row: WishlistRow) -> bool:
    if product.size_kind == "potted":
        if row.min_litres is None:
            return True
        return product.pot_size_litres is not None \
               and product.pot_size_litres >= row.min_litres
    if product.size_kind in ("bare_root", "rootball"):
        return row.allow_bare_root
    if product.size_kind == "unknown":
        # only permissive rows accept unknowns
        return row.min_litres is None and row.allow_bare_root
    return False  # non_plant
```

---

## 6. State & persistence

### 6.1 Models (`src/wishlist/models.py`)

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass
class PlantSelector:
    kind: Literal["cultivar", "species", "genus", "category"]
    genus: str | None
    species: str | None
    cultivar: str | None
    category: str | None
    label: str

@dataclass
class WishlistRow:
    id: str               # uuid4 — stable across reruns
    selector: PlantSelector
    qty: int
    min_litres: float | None
    allow_bare_root: bool
    added_at: datetime

@dataclass
class Wishlist:
    rows: list[WishlistRow]
    notes: str
    updated_at: datetime
```

### 6.2 Two-layer persistence

- **In-session: `st.session_state["wishlist"]`** holds the live `Wishlist`. Streamlit reruns the script on every interaction; `session_state` is what survives reruns and tab switches.
- **Cross-session: `.wishlist.json`** in the project root (gitignored). Auto-written on every mutation; auto-read on startup. Plain JSON; datetimes as ISO 8601; enums as strings.

### 6.3 Atomic write

Write to `.wishlist.json.tmp`, fsync, rename over `.wishlist.json`. Prevents corruption if Streamlit crashes mid-write. On startup, if `.wishlist.json` is unreadable, try `.wishlist.json.tmp` once, else load an empty wishlist with a toast: "Couldn't restore previous wishlist."

### 6.4 No URL/query-param state

Single-user, single-machine — query-param sharing adds complexity without payoff.

---

## 7. Streamlit app structure

### 7.1 Tabs

```
┌──────────────────────────────────────────────────────────┐
│  Blaithin · Wishlist                                     │
│                                                          │
│  [ Build ]  [ Browse ]  [ Plans ]                        │
└──────────────────────────────────────────────────────────┘
```

Three tabs; active tab survives reruns via `session_state["active_tab"]`.

### 7.2 Build tab

Two zones: add-row form, and the editable wishlist table.

```
┌─ Add to wishlist ──────────────────────────────────────────┐
│ Plant:    [ Acer palmatum 'Bloodgood'           ▾  ]       │
│           Search hits (type to filter):                    │
│             ▸ Acer palmatum 'Bloodgood'   cultivar (8)     │
│             ▸ Acer palmatum « any »       species   (12)   │
│             ▸ Acer « any »                genus     (28)   │
│             ▸ [Hedging mix]               category  (4)    │
│ Qty: [ 2 ]   Min L: [   ]   ☑ Allow bare-root  [ + Add ]   │
└────────────────────────────────────────────────────────────┘

┌─ Your wishlist (3 rows) ──────────────────────────────────┐
│ Plant                       │ Qty │ Min L │ BR? │   ✕     │
│ Acer palmatum 'Bloodgood'   │  2  │   3   │  ☐  │   🗑    │
│ Rosa 'Gertrude Jekyll'      │  3  │       │  ☑  │   🗑    │
│ Lavandula a. 'Hidcote'      │  6  │   1   │  ☐  │   🗑    │
└───────────────────────────────────────────────────────────┘

  Notes: [ free-text textarea, persisted in JSON ]

  [ Clear all ]   [ Export CSV ]            [ Find best prices → ]
```

- **Autocomplete:** `st.selectbox` driven by a cached list. Built once per session by `src/wishlist/candidates.py` from the union of distinct `(genus, species, cultivar)` tuples in `products_matched`, plus species-level "any" entries, plus genus-level "any" entries, plus a small fixed set of categories derived from `product_category` (e.g. `[Hedging mix]`, `[Native wildflower mix]`, `[Bulb mixed]`). Each entry stores the nursery-count for display.
- **Wishlist table:** `st.data_editor` with typed columns: `qty` int (min 1), `min_litres` float (nullable, min 0), `allow_bare_root` bool, plus a delete checkbox / column. Edits write back through `session_state` and trigger the JSON save.
- **`Find best prices →`** runs the optimiser and switches to the Plans tab.

### 7.3 Browse tab

Replaces the deleted Observable Plants page. Sidebar filters drive a polars query on `products_matched.parquet`; results in `st.dataframe`.

```
┌─ Filters ─────────┐  ┌─ Results (sorted by price) ──────────────┐
│ Genus: [Acer  ]   │  │ Plant            Nursery  Size  €    +   │
│ Species: [...]    │  │ Acer pal Blood.  Tully's  3L   45 [+]   │
│ Source: [all  ▾] │  │ Acer pal Blood.  Newland  5L   62 [+]   │
│ Plant type: [▾]  │  │ Acer pal Atrop.  Famous   BR   18 [+]   │
│ ☐ In stock only   │  │ Acer palmatum    Hedgie   2L   12 [+]   │
│ Hardiness ≥ [H6▾]│  │                                          │
│ Max €: [   ]      │  │                                          │
└───────────────────┘  └──────────────────────────────────────────┘
```

Each row has an inline `+` button that opens a small `st.popover` with qty / min_litres / allow_bare_root pre-filled for that plant, plus an "Add to wishlist" submit. On success: `st.toast("Added Acer palmatum 'Bloodgood' ×2")`.

The Add-from-Browse popover constructs a `PlantSelector` at the most specific level available for the clicked row (cultivar if present, else species).

### 7.4 Plans tab

Empty state (no wishlist rows yet): "Add rows on the Build tab, then click Find best prices."
Populated state: as section 9.

---

## 8. Optimiser engine

### 8.1 Algorithm

Three stages.

**Stage 1 — candidates per wishlist row** (`src/wishlist/candidates.py`):

For each `WishlistRow`:
- filter `products_matched` to `is_plant = true` AND matches the `PlantSelector`
  - `cultivar`: genus + species + cultivar all equal
  - `species`: genus + species equal, any cultivar
  - `genus`: genus equal, any species/cultivar
  - `category`: `product_category` equal
- apply `fits_constraint(product, row)` predicate (size_kind + min_litres + allow_bare_root)
- apply currency conversion to EUR via `src/wishlist/fx.py`
- apply VAT uplift (×1.23) for nurseries with `vat_included: false`
- drop products from nurseries where known `stock < qty` (treat null stock as available)

Result: `candidates[row_id] = list[Product]`.

**Stage 2 — cheapest-per-nursery per row** (`src/wishlist/optimizer.py`):

For each `(row_id, nursery_id)`: keep the cheapest qualifying product.

Result: `cheapest[row_id] = dict[nursery_id, Product]`.

**Stage 3 — subset enumeration** (`src/wishlist/optimizer.py`):

```
candidate_nurseries = ⋃_row keys(cheapest[row])
for each non-empty subset S ⊆ candidate_nurseries with |S| ≤ 8:
    for each row:
        if S ∩ keys(cheapest[row]) is empty: row is unfulfilled in this subset
        else: assign row to argmin_{n ∈ S ∩ keys(cheapest[row])} price_eur(n)
    group → baskets[nursery] = list[(row, product, qty)]
    for each basket:
        subtotal_eur = Σ qty × unit_price_eur
        shipping_eur = shipping(subtotal_eur, nurseries[nursery])
        if shipping_eur is None:           # min_order failed
            mark subset infeasible and break
    total_eur = Σ subtotal + Σ shipping
    record Plan(subset, baskets, total_eur, unfulfilled_rows)
```

For a 15-row wishlist with 12 candidate nurseries: ≈4k subsets, ~50ms. If candidates exceed 30: hard cap at `|S| ≤ 8` with a warning banner (greedy fallback documented but not implemented in MVP — see §10.2 hard cap).

### 8.2 Plan selection

Optimiser returns all feasible plans, ranked by `total_eur`. The Plans tab UI (§9) uses a slider over `max_nurseries ∈ [1, 8]` to pick the cheapest plan with `len(baskets) ≤ slider_value`. A precomputed trade-off curve maps every value of the slider to its corresponding cheapest plan.

### 8.3 Shipping (`src/wishlist/shipping.py`)

Dispatches on `delivery_type` from `nurseries.yaml`:

| type | rule |
|---|---|
| `free` | `0` |
| `flat` | `fees[0].fee_eur` |
| `tiered` | sort `fees` by `max_value_eur` asc (None = ∞ ceiling); pick the first bucket where `subtotal ≤ ceiling` |
| `per_box` | `delivery_per_box_eur`, assume one box (GreenGarden only; B2B edge case OK to approximate) |

After computing the fee, enforce `min_order_eur` as a hard cutoff. If `subtotal < min_order_eur`: return `None` → optimiser drops the subset.

### 8.4 FX (`src/wishlist/fx.py`)

Reads `data/fx.parquet` and exposes `convert(value_native, currency) -> float`. EUR returns unchanged. Missing rate for a currency: raise a defined exception; optimiser surfaces "X products excluded — FX rate for GBP missing" in the Plans tab and excludes the affected products from candidates.

### 8.5 Caching

The optimiser is pure. Wrapped in `@st.cache_data` keyed on `(wishlist hash, products_matched mtime, nurseries.yaml mtime, fx.parquet mtime)`. Reruns are instant unless inputs change.

---

## 9. Plan output UI

### 9.1 Slider + chosen plan

```
┌─ Max nurseries: ──────●────────  [ 3 ]   ←──── Slider 1..8 ─┐
│                                                              │
│  Cheapest plan using ≤ 3 nurseries:                          │
│  ┌─ Tully's Nurseries ─── 📅 scraped 8 days ago ────────┐   │
│  │  shop.tullynurseries.ie   EUR · VAT added (ex-VAT)   │   │
│  │  Plant                   │ Size  │ Qty │  Unit € │ … │   │
│  │  Acer pal. 'Bloodgood'   │   3 L │  2  │  22.50  │ … │   │
│  │  ...                                                  │   │
│  │  Subtotal (incl. 23% VAT)                  128.40    │   │
│  │  Shipping: tiered €60 ≤ €600                60.00    │   │
│  │  Basket total                              €188.40    │   │
│  │  [ Open all 4 product pages in tabs ]                 │   │
│  └────────────────────────────────────────────────────────┘  │
│  (… one card per nursery in the basket …)                    │
│                                                              │
│  Plan total to door: €268.20    All 12 rows fulfilled        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 Trade-off curve

Compact table below the chosen plan:

```
Trade-off curve:
Max nurseries │ Total (€) │ Items fulfilled │ Δ vs cap=8
──────────────┼───────────┼─────────────────┼───────────
     1        │  292.40   │    9 / 12       │  +45.10
     2        │  281.60   │   12 / 12       │  +34.30
 →   3        │  268.20   │   12 / 12       │  +20.90
     4        │  254.10   │   12 / 12       │   +6.80
     5        │  249.30   │   12 / 12       │   +2.00
     6        │  247.30   │   12 / 12       │      —
     7        │  247.30   │   12 / 12       │      —
     8        │  247.30   │   12 / 12       │      —
```

Clicking a row jumps the slider to that value.

### 9.3 Couldn't-find section

```
▾ Couldn't fulfil 1 row at Max=3
   • Acer palmatum 'Mikawa-yatsubusa' (qty 1, ≥3L)
     Available at: Famous Roses €34 + €18 ship
     → expands to 4 nurseries: total €298.10
     [ Expand cap to 4 ]
```

"Expand cap" is a button that nudges the slider to the smallest value that fulfils the row.

### 9.4 Plan-wide actions

```
[ Export plan as CSV ]    [ Copy summary to clipboard ]    [ Open all baskets ]
```

CSV columns: `nursery, product_name, size, qty, unit_price_native, currency, unit_price_eur, line_eur, product_url`.
Summary clipboard format: short plaintext, one line per basket, totals at end.
Open-all-baskets: `webbrowser.open_new_tab(url)` for every product URL in the plan.

### 9.5 Badges

- **Freshness:** `(today - input_date).days` → "scraped N days ago" badge on each basket card.
- **VAT:** "VAT added" if `nurseries[id].vat_included == false`, else "VAT incl.".
- **Currency:** show native currency in the basket header if not EUR.

---

## 10. Error handling

### 10.1 Failure modes

| Failure | Behaviour |
|---|---|
| `products_matched.parquet` missing | App startup error: "Run `python load_bronze_data.py --matching` first." |
| `nurseries.yaml` malformed | Fail at startup with file + line number; do not silently load partial. |
| `.wishlist.json` corrupt | Try `.wishlist.json.tmp` fallback; else empty list + one-time toast. |
| Wishlist row's plant identity not present in current data | Mark row "⚠ no longer in data"; optimiser treats as unfulfillable. |
| FX rate missing for a currency | Skip those products; log to stderr; surface "X products excluded — FX rate for GBP missing" in the Plans tab. |
| Optimiser exceeds 5s | Hard cap `\|S\| ≤ 8`; if still slow with ≥30 candidate nurseries, return greedy assignment with a warning banner. |
| Streamlit reruns mid-save | Atomic rename pattern (§6.3) prevents partial writes. |

### 10.2 Edge cases

- **Empty wishlist** → Plans tab shows "Add rows to your wishlist to see plans." No optimiser call.
- **All rows unfulfillable** → Plans tab shows the slider but with one row: "No nursery fulfils any of these rows." Couldn't-find section is populated.
- **Same plant twice with different size constraints** → kept as separate rows (deliberate).
- **`qty=0`** → invalidated at edit time via `data_editor` column_config (`min_value=1`).
- **Unknown `size_kind` with restrictive constraint** → row rejects; permissive rows accept (matches `fits_constraint` predicate).
- **Bulk packs (`products_matched.quantity > 1`)** → ignored in MVP; every product treated as one unit. Bulbi 50-packs etc. will quote the pack price against a single-unit wishlist row, which is correct-but-misleading. Future work: round purchases up by pack size and surface "over-purchasing" in basket cards.
- **`stock` is a String column in current data** (`"1"`, `"2"`, `""`, etc.). Parse to `int` defensively; treat non-numeric as null/unknown.

---

## 11. Testing

### 11.1 Layout

```
tests/wishlist/
  test_sizes.py        — golden inputs from real scraped data
  test_shipping.py     — every delivery_type × edge cases + min_order
  test_candidates.py   — PlantSelector resolution per granularity
                       + fits_constraint() truth table
  test_optimizer.py    — small hand-built fixtures with known optimal
  test_state.py        — Wishlist ↔ JSON roundtrip + atomic write
  test_fx.py           — conversion + missing-rate raises
  test_size_normalize.py — pipeline step end-to-end on a mini parquet
  fixtures/
    mini_products.parquet
    mini_nurseries.yaml
    mini_fx.parquet
```

### 11.2 Coverage targets

- `test_sizes.py` covers every parse branch in `size_normalize.py` with at least one real example from `data/*/data.parquet`.
- `test_shipping.py` covers all four delivery types, both sides of every tier boundary, exact-equal-to-min_order, below-min_order.
- `test_optimizer.py` includes at least one case where the tiered-shipping free-over-X threshold dominates choice — proves shipping is not just a sum of flat fees.
- `test_state.py` simulates a crashed write (truncated `.tmp`) and verifies recovery to `.wishlist.json`.

### 11.3 Manual smoke pass

Before each release:

```
streamlit run scripts/wishlist.py
1. Add 3 wishlist rows (one cultivar, one species-level, one category)
2. Verify Build/Browse/Plans tabs all render and switch
3. Move max-nurseries slider end-to-end; trade-off table responds
4. Export plan CSV; confirm columns and rows
5. Close app, reopen — list persists
```

### 11.4 Performance assertion

`test_optimizer.py::test_perf_20_rows_15_nurseries` — generate a synthetic wishlist of 20 rows resolving to 15 candidate nurseries; assert optimisation completes in < 1s on the dev machine.

---

## 12. Cleanup of legacy dashboard

Part of this work, done as the first commit before any new code lands:

- Delete `site/` directory entirely.
- Delete `.github/workflows/deploy.yml` if present (and any other workflow exclusively serving the Pages deployment).
- Update `README.md`:
  - Remove the dashboard URL line.
  - Remove the `cd site && npm install && npm run dev` step.
  - Remove the `site/` line from the Layout section.
  - Add a `streamlit run scripts/wishlist.py` example to the Run-locally section.
- Update `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` with a short addendum at the top noting that Sub-project 3 (Dashboard) is superseded by this wishlist-optimiser spec.
- User performs the GitHub-side step manually: disable GitHub Pages under repo Settings → Pages.

`.gitignore` additions:

```
.wishlist.json
.wishlist.json.tmp
```

---

## 13. File layout summary

```
Repository deltas:

  DELETE  site/
  DELETE  .github/workflows/deploy.yml         (if present)

  MODIFY  README.md                            (remove Pages refs; add streamlit example)
  MODIFY  .gitignore                           (add .wishlist.json[.tmp])
  MODIFY  docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md  (addendum)

  NEW     src/transforms/__init__.py
  NEW     src/transforms/size_normalize.py
  NEW     src/wishlist/__init__.py
  NEW     src/wishlist/models.py
  NEW     src/wishlist/sizes.py
  NEW     src/wishlist/candidates.py
  NEW     src/wishlist/optimizer.py
  NEW     src/wishlist/shipping.py
  NEW     src/wishlist/fx.py
  NEW     src/wishlist/state.py
  NEW     scripts/wishlist.py
  NEW     tests/wishlist/                      (test_*.py + fixtures/)

  MODIFY  load_bronze_data.py                  (hook size_normalize into --matching path)
  MODIFY  requirements.txt                     (+ streamlit)
```

---

## 14. Implementation order

Suggested commit/task sequence — details in the implementation plan:

1. **Cleanup commit** — delete `site/`, update README, update redesign spec addendum, add `.gitignore` entries.
2. **`size_normalize.py`** + unit tests + hook into matching pipeline.
3. **`src/wishlist/models.py`** + `state.py` + roundtrip tests.
4. **`src/wishlist/sizes.py`** + `fits_constraint` tests.
5. **`src/wishlist/fx.py`** + tests.
6. **`src/wishlist/candidates.py`** + tests.
7. **`src/wishlist/shipping.py`** + tests covering all delivery types and min_order.
8. **`src/wishlist/optimizer.py`** + tests (small fixtures, performance assertion).
9. **`scripts/wishlist.py` — Build tab + state wiring.**
10. **`scripts/wishlist.py` — Browse tab.**
11. **`scripts/wishlist.py` — Plans tab (slider + trade-off table + basket cards + couldn't-find + exports).**
12. **Manual smoke pass; freshness/VAT/currency badges polish.**
