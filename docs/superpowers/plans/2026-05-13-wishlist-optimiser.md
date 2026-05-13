# Wishlist Optimiser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Streamlit app that takes a plant wishlist (qty, min litres, allow-bare-root) and outputs the cheapest nursery-subset plan to door, factoring in tiered shipping, min-order, FX, and VAT. Also: delete the legacy Observable Framework site.

**Architecture:** Pure-Python core (sizes, candidates, shipping, optimiser) tested with pytest. Streamlit shell on top for UI. All compute is local; persistence via `.wishlist.json`. One new pipeline step (`src/transforms/size_normalize.py`) adds `pot_size_litres` + `size_kind` columns to `data/products_matched.parquet`.

**Tech Stack:** Python 3.11+, polars==0.20.16, pydantic v2, pyyaml, streamlit, pytest. Reuses existing `src/common/fx.py` and `src/common/nurseries.py`.

**Spec:** `docs/superpowers/specs/2026-05-13-wishlist-optimiser-design.md`

---

## Task 1: Cleanup — delete legacy site, update workflows, README, .gitignore

**Files:**
- Delete: `site/` (entire directory recursively)
- Delete: `.github/workflows/deploy.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `.gitignore`
- Modify: `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` (add addendum)

- [ ] **Step 1: Delete the `site/` directory recursively**

```bash
git rm -r site/
```

- [ ] **Step 2: Delete the GitHub Pages deploy workflow**

```bash
git rm .github/workflows/deploy.yml
```

- [ ] **Step 3: Remove the `build-site` job from `.github/workflows/ci.yml`**

Edit `.github/workflows/ci.yml` to remove lines 16–24 (the entire `build-site:` job). Resulting file:

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: pytest -v
```

- [ ] **Step 4: Update `README.md`**

Replace the entire current contents of `README.md` with:

```markdown
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
```

- [ ] **Step 5: Update `.gitignore`**

Remove the now-obsolete Observable Framework section (lines 138–144 currently):

```
# Observable Framework
site/node_modules/
site/dist/
site/.observablehq/
```

Add the wishlist state files in the same section's place:

```
# Wishlist optimiser local state
.wishlist.json
.wishlist.json.tmp
```

- [ ] **Step 6: Add addendum to the redesign spec**

Open `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` and insert at the very top, after the existing `# Blaithin Redesign — Design Spec` line:

```markdown
> **2026-05-13 addendum:** Sub-project 3 (Dashboard — Observable Framework) is superseded by the wishlist optimiser spec at `docs/superpowers/specs/2026-05-13-wishlist-optimiser-design.md`. The Observable site is being deleted; comparison work happens in a local Streamlit app instead. Sub-projects 0, R, 2, 1, 4 remain in effect.
```

- [ ] **Step 7: Commit cleanup**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: remove legacy Observable Framework site

Drops site/ entirely, the Pages deploy workflow, the build-site CI job,
and the dashboard references in README. Adds wishlist state files to
.gitignore in preparation for the new local optimiser app.

The 2026-05-11 redesign spec gets an addendum noting that sub-project 3
(Dashboard) is superseded by the wishlist optimiser spec.
EOF
)"
```

- [ ] **Step 8: Verify nothing left behind**

```bash
ls site/ 2>&1 || echo "site removed OK"
ls .github/workflows/
grep -i observable README.md .gitignore || echo "no stray references"
```

Expected: `site removed OK`, only `ci.yml` in workflows, no Observable references.

---

## Task 2: Pot-size lookup tables (no constraints yet)

**Files:**
- Create: `src/wishlist/__init__.py`
- Create: `src/wishlist/sizes.py`
- Create: `tests/wishlist/__init__.py`
- Create: `tests/wishlist/test_sizes.py`

- [ ] **Step 1: Write the failing test for `CM_TO_LITRES`**

Create `tests/wishlist/__init__.py` as an empty file. Then create `tests/wishlist/test_sizes.py`:

```python
"""Tests for cm and pot-code lookup tables."""

from src.wishlist.sizes import CM_TO_LITRES, POT_CODE_TO_CM


def test_cm_lookup_covers_7_to_50_inclusive():
    assert set(CM_TO_LITRES.keys()) == set(range(7, 51))


def test_cm_lookup_values_are_integers():
    assert all(isinstance(v, int) for v in CM_TO_LITRES.values())


def test_cm_lookup_monotonic_non_decreasing():
    sorted_keys = sorted(CM_TO_LITRES.keys())
    prev = -1
    for k in sorted_keys:
        assert CM_TO_LITRES[k] >= prev, f"{k}cm -> {CM_TO_LITRES[k]}L is less than previous"
        prev = CM_TO_LITRES[k]


def test_cm_lookup_known_anchors():
    # Anchors from spec §5.3
    assert CM_TO_LITRES[7] == 0
    assert CM_TO_LITRES[9] == 1
    assert CM_TO_LITRES[11] == 1
    assert CM_TO_LITRES[15] == 2
    assert CM_TO_LITRES[18] == 3
    assert CM_TO_LITRES[25] == 10
    assert CM_TO_LITRES[30] == 15
    assert CM_TO_LITRES[50] == 63


def test_pot_code_lookup_covers_known_codes():
    expected = {
        "P8.5", "P9", "P9.5",
        "P10", "P11", "P12", "P13", "P14", "P15",
        "P16", "P17", "P18", "P19", "P20",
        "P25", "P30",
    }
    assert set(POT_CODE_TO_CM.keys()) == expected


def test_pot_code_values_are_in_cm_table():
    # Every P-code must map to a cm value that exists in CM_TO_LITRES.
    for code, cm in POT_CODE_TO_CM.items():
        assert cm in CM_TO_LITRES, f"{code} -> {cm}cm not in CM_TO_LITRES"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/wishlist/test_sizes.py -v`
Expected: FAIL — module `src.wishlist.sizes` not found.

- [ ] **Step 3: Implement `src/wishlist/sizes.py`**

Create `src/wishlist/__init__.py` as an empty file. Then create `src/wishlist/sizes.py`:

```python
"""Pot-size lookup tables and constraint matching.

The single source of truth for diameter -> volume is ``CM_TO_LITRES``.
Pot codes (P9, P11, ...) funnel through ``POT_CODE_TO_CM`` first, so the
same physical pot always returns the same litre value regardless of how
the nursery labelled it.

The values are an approximation built from V ~= 0.5 * (d/10)^3, rounded
to integer litres. They differ from the historical stg_products.sql
mapping at some P-codes; internal consistency is favoured over matching
the older industry table. See spec §5.3 for the derivation.
"""

from __future__ import annotations


CM_TO_LITRES: dict[int, int] = {
    7: 0,  8: 0,  9: 1, 10: 1, 11: 1, 12: 1, 13: 1, 14: 2, 15: 2,
    16: 2, 17: 2, 18: 3, 19: 3, 20: 4, 21: 5, 22: 5, 23: 7, 24: 8,
    25: 10, 26: 11, 27: 12, 28: 13, 29: 14, 30: 15,
    31: 16, 32: 17, 33: 18, 34: 20, 35: 21, 36: 23, 37: 25, 38: 27,
    39: 30, 40: 32, 41: 35, 42: 37, 43: 40, 44: 43, 45: 46,
    46: 49, 47: 52, 48: 55, 49: 59, 50: 63,
}


POT_CODE_TO_CM: dict[str, int] = {
    "P8.5": 8, "P9": 9, "P9.5": 9,
    "P10": 10, "P11": 11, "P12": 12, "P13": 13, "P14": 14, "P15": 15,
    "P16": 16, "P17": 17, "P18": 18, "P19": 19, "P20": 20,
    "P25": 25, "P30": 30,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/wishlist/test_sizes.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/wishlist/__init__.py src/wishlist/sizes.py tests/wishlist/__init__.py tests/wishlist/test_sizes.py
git commit -m "wishlist: cm + pot-code lookup tables"
```

---

## Task 3: Size normaliser pipeline step

**Files:**
- Create: `src/transforms/__init__.py`
- Create: `src/transforms/size_normalize.py`
- Create: `tests/transforms/__init__.py`
- Create: `tests/transforms/test_size_normalize.py`

- [ ] **Step 1: Write failing tests for the parser**

Create `tests/transforms/__init__.py` as an empty file. Create `tests/transforms/test_size_normalize.py`:

```python
"""Tests for the size_normalize pipeline step.

Tests the pure parsing function on realistic size strings drawn from
data/*/data.parquet. Tests for the DataFrame-level transform separately.
"""

import polars as pl
import pytest

from src.transforms.size_normalize import (
    SizeKind,
    add_size_columns,
    parse_size,
)


# --- parse_size ----------------------------------------------------------------


@pytest.mark.parametrize("size_str,is_plant,expected_kind,expected_litres", [
    # Non-plant short-circuits before any string match.
    ("2 Litre", False, "non_plant", None),
    ("", False, "non_plant", None),
    # Bare root and rootball go categorical.
    ("Bare Root", True, "bare_root", None),
    ("bare root", True, "bare_root", None),
    ("Rootball", True, "rootball", None),
    ("Rootball + Pot", True, "rootball", None),
    # Litre values, exact and ranges.
    ("2 Litre", True, "potted", 2.0),
    ("2L", True, "potted", 2.0),
    ("2.5 ltr", True, "potted", 2.5),
    ("7.5-10 Litre", True, "potted", 7.5),
    ("10-15 Litre", True, "potted", 10.0),
    ("30-35 Litre", True, "potted", 30.0),
    # Pot codes.
    ("P9", True, "potted", 1.0),       # 9cm -> 1L per CM_TO_LITRES
    ("P11", True, "potted", 1.0),
    ("P15", True, "potted", 2.0),
    ("P25", True, "potted", 10.0),
    # cm values.
    ("9cm", True, "potted", 1.0),
    ("9 cm", True, "potted", 1.0),
    ("9.5cm", True, "potted", 1.0),    # rounds half-up to 10cm = 1L
    ("15cm", True, "potted", 2.0),
    # Out of range cm -> unknown.
    ("5cm", True, "unknown", None),
    ("60cm", True, "unknown", None),
    # Unmatched / vague.
    ("Half Standard", True, "unknown", None),
    ("in cont.", True, "unknown", None),
    ("Tree", True, "unknown", None),
    ("", True, "unknown", None),
    (None, True, "unknown", None),
])
def test_parse_size(size_str, is_plant, expected_kind, expected_litres):
    kind, litres = parse_size(size_str, is_plant=is_plant)
    assert kind == expected_kind
    assert litres == expected_litres


# --- DataFrame-level transform ------------------------------------------------


def test_add_size_columns_adds_two_new_columns():
    df = pl.DataFrame({
        "size": ["2 Litre", "Bare Root", None, "P15"],
        "is_plant": [True, True, True, True],
        "other_col": [1, 2, 3, 4],
    })
    out = add_size_columns(df)
    assert "pot_size_litres" in out.columns
    assert "size_kind" in out.columns
    assert out["pot_size_litres"].to_list() == [2.0, None, None, 2.0]
    assert out["size_kind"].to_list() == ["potted", "bare_root", "unknown", "potted"]
    # Other columns preserved.
    assert "other_col" in out.columns


def test_add_size_columns_non_plants_get_non_plant_kind():
    df = pl.DataFrame({
        "size": ["10 Litre", "Compost"],
        "is_plant": [True, False],
    })
    out = add_size_columns(df)
    assert out["size_kind"].to_list() == ["potted", "non_plant"]
    assert out["pot_size_litres"].to_list() == [10.0, None]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/transforms/test_size_normalize.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/transforms/size_normalize.py`**

Create `src/transforms/__init__.py` as an empty file. Create `src/transforms/size_normalize.py`:

```python
"""Normalise the raw ``size`` string column into structured columns.

Reads ``data/products_matched.parquet`` (or any DataFrame with ``size`` +
``is_plant``) and adds two columns:

- ``pot_size_litres``: Float | None
- ``size_kind``: one of ``potted``, ``bare_root``, ``rootball``,
  ``unknown``, ``non_plant``

Designed to run after the matching pipeline. See spec §5 for the
parser semantics and the cm/pot-code tables.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import polars as pl

from src.wishlist.sizes import CM_TO_LITRES, POT_CODE_TO_CM

SizeKind = Literal["potted", "bare_root", "rootball", "unknown", "non_plant"]

PRODUCTS_PARQUET = Path(__file__).resolve().parents[2] / "data" / "products_matched.parquet"


_RE_BARE_ROOT = re.compile(r"bare\s*root", re.IGNORECASE)
_RE_ROOTBALL = re.compile(r"rootball", re.IGNORECASE)
_RE_LITRE_RANGE = re.compile(r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*(?:L|Lit)", re.IGNORECASE)
_RE_LITRE_SINGLE = re.compile(r"(\d+\.?\d*)\s*(?:L|Lit)", re.IGNORECASE)
_RE_POT_CODE = re.compile(r"\bP(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_RE_CM = re.compile(r"(\d+(?:\.\d+)?)\s*cm", re.IGNORECASE)


def parse_size(size_str: str | None, *, is_plant: bool) -> tuple[SizeKind, float | None]:
    """Parse a single ``size`` cell into ``(size_kind, pot_size_litres)``.

    Always returns ("non_plant", None) when ``is_plant`` is False.
    Returns ("unknown", None) for empty / None / unparsable strings.
    """

    if not is_plant:
        return "non_plant", None
    if size_str is None or not size_str.strip():
        return "unknown", None

    s = size_str.strip()

    # Order matters: bare-root / rootball strings can contain digits we
    # don't want to interpret as litres.
    if _RE_BARE_ROOT.search(s):
        return "bare_root", None
    if _RE_ROOTBALL.search(s):
        return "rootball", None

    if m := _RE_LITRE_RANGE.search(s):
        return "potted", float(m.group(1))   # lower bound
    if m := _RE_LITRE_SINGLE.search(s):
        return "potted", float(m.group(1))
    if m := _RE_POT_CODE.search(s):
        code = "P" + m.group(1)
        cm = POT_CODE_TO_CM.get(code)
        if cm is None:
            return "unknown", None
        return "potted", float(CM_TO_LITRES[cm])
    if m := _RE_CM.search(s):
        cm_rounded = round(float(m.group(1)))
        if cm_rounded not in CM_TO_LITRES:
            return "unknown", None
        return "potted", float(CM_TO_LITRES[cm_rounded])

    return "unknown", None


def add_size_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Return a copy of ``df`` with ``pot_size_litres`` and ``size_kind`` added.

    Expects columns ``size`` (String, nullable) and ``is_plant`` (Boolean).
    """

    pairs = [parse_size(s, is_plant=p) for s, p in zip(df["size"].to_list(), df["is_plant"].to_list())]
    kinds = [k for k, _ in pairs]
    litres = [v for _, v in pairs]
    return df.with_columns([
        pl.Series("size_kind", kinds, dtype=pl.String),
        pl.Series("pot_size_litres", litres, dtype=pl.Float64),
    ])


def run() -> None:
    """Read products_matched.parquet, add the size columns, write back."""

    df = pl.read_parquet(PRODUCTS_PARQUET)
    out = add_size_columns(df)
    out.write_parquet(PRODUCTS_PARQUET)
    print(f"Wrote {len(out)} rows -> {PRODUCTS_PARQUET}")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/transforms/test_size_normalize.py -v`
Expected: PASS (all parametrised cases + 2 DataFrame tests).

- [ ] **Step 5: Commit**

```bash
git add src/transforms/__init__.py src/transforms/size_normalize.py tests/transforms/__init__.py tests/transforms/test_size_normalize.py
git commit -m "transforms: size_normalize pipeline step

Adds pot_size_litres + size_kind columns to products_matched.parquet
based on the cm and pot-code lookup tables. Range handling takes the
lower bound; out-of-range / unparsable strings become 'unknown'."
```

---

## Task 4: Hook size_normalize into the matching pipeline

**Files:**
- Modify: `load_bronze_data.py:83-109` (the `_run_matching` function)

- [ ] **Step 1: Update `_run_matching` to call `add_size_columns` before write**

Edit `load_bronze_data.py`. Replace the `_run_matching` function (lines 83–109) with:

```python
def _run_matching(*, llm_enabled: bool) -> None:
    """Load latest per-nursery parquets + RHS, run the matching pipeline, write output."""

    from src.matching.run import run_with_llm_fallback
    from src.transforms.size_normalize import add_size_columns

    frames = []
    for nursery in SCRAPED_NURSERIES:
        nursery_dir = Path(f"data/{nursery}")
        parquets = sorted(nursery_dir.glob("*.parquet"))
        if not parquets:
            print(f"No parquets for {nursery}, skipping.")
            continue
        df = pl.read_parquet(parquets[-1]).with_columns(pl.lit(nursery).alias("source"))
        if "product_name" in df.columns and "product_name_raw" not in df.columns:
            df = df.rename({"product_name": "product_name_raw"})
        frames.append(df)

    if not frames:
        raise SystemExit("No nursery parquets found — run scrapes first.")

    products_df = pl.concat(frames, how="diagonal_relaxed")
    rhs_df = pl.read_parquet("data/rhs/data.parquet")

    matched = run_with_llm_fallback(products_df, rhs_df, llm_enabled=llm_enabled)
    matched = add_size_columns(matched)

    out = Path("data/products_matched.parquet")
    matched.write_parquet(out)
    print(f"Wrote {len(matched)} matched products -> {out}")
```

- [ ] **Step 2: Spot-check existing parquet picks up the new columns when re-run**

This step is manual — run the matching pipeline once to refresh the parquet with new columns:

```bash
python load_bronze_data.py --matching --no-llm
```

Expected output line: `Wrote N matched products -> data\products_matched.parquet`.

- [ ] **Step 3: Verify columns are present**

```bash
.venv/Scripts/python.exe -c "import polars as pl; df = pl.read_parquet('data/products_matched.parquet'); print(sorted(df.columns)); print(df['size_kind'].value_counts())"
```

Expected: `pot_size_litres` and `size_kind` in columns; non-zero counts for `potted`, `unknown`, `non_plant` at minimum.

- [ ] **Step 4: Commit**

```bash
git add load_bronze_data.py data/products_matched.parquet
git commit -m "load: hook size_normalize into --matching path"
```

---

## Task 5: Wishlist data models

**Files:**
- Create: `src/wishlist/models.py`
- Create: `tests/wishlist/test_models.py`

- [ ] **Step 1: Write failing tests for the models**

Create `tests/wishlist/test_models.py`:

```python
"""Tests for wishlist dataclasses — basic instantiation + identity."""

from datetime import datetime

import pytest

from src.wishlist.models import PlantSelector, Wishlist, WishlistRow


def test_plant_selector_cultivar_kind():
    s = PlantSelector(
        kind="cultivar",
        genus="Acer",
        species="palmatum",
        cultivar="Bloodgood",
        category=None,
        label="Acer palmatum 'Bloodgood'",
    )
    assert s.kind == "cultivar"
    assert s.label == "Acer palmatum 'Bloodgood'"


def test_plant_selector_category_kind():
    s = PlantSelector(
        kind="category",
        genus=None,
        species=None,
        cultivar=None,
        category="hedging_mix",
        label="[Hedging mix]",
    )
    assert s.kind == "category"
    assert s.category == "hedging_mix"


def test_wishlist_row_basic():
    sel = PlantSelector(
        kind="species",
        genus="Acer",
        species="palmatum",
        cultivar=None,
        category=None,
        label="Acer palmatum (any cultivar)",
    )
    row = WishlistRow(
        id="abc-123",
        selector=sel,
        qty=2,
        min_litres=3.0,
        allow_bare_root=False,
        added_at=datetime(2026, 5, 13, 12, 0, 0),
    )
    assert row.qty == 2
    assert row.min_litres == 3.0
    assert row.allow_bare_root is False


def test_wishlist_empty():
    wl = Wishlist(rows=[], notes="", updated_at=datetime(2026, 5, 13))
    assert wl.rows == []
    assert wl.notes == ""


def test_wishlist_with_rows():
    sel = PlantSelector("genus", "Rosa", None, None, None, "Rosa (any)")
    row = WishlistRow("id1", sel, 5, None, True, datetime(2026, 5, 13))
    wl = Wishlist(rows=[row], notes="Spring 2026", updated_at=datetime(2026, 5, 13))
    assert len(wl.rows) == 1
    assert wl.rows[0].selector.genus == "Rosa"
    assert wl.notes == "Spring 2026"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/wishlist/test_models.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/wishlist/models.py`**

```python
"""Wishlist core data structures.

Plain dataclasses — no validation logic beyond Python's. Round-trip
through JSON is handled in ``state.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


PlantSelectorKind = Literal["cultivar", "species", "genus", "category"]
SizeKind = Literal["potted", "bare_root", "rootball", "unknown", "non_plant"]


@dataclass
class PlantSelector:
    """The plant identity a wishlist row is asking for.

    Four levels of granularity. ``label`` is the display string shown in
    the UI; the other fields are what the optimiser filters on.
    """

    kind: PlantSelectorKind
    genus: str | None
    species: str | None
    cultivar: str | None
    category: str | None
    label: str


@dataclass
class WishlistRow:
    """One desired plant in the wishlist."""

    id: str               # uuid4, stable across reruns
    selector: PlantSelector
    qty: int
    min_litres: float | None
    allow_bare_root: bool
    added_at: datetime


@dataclass
class Wishlist:
    """The user's complete wishlist."""

    rows: list[WishlistRow]
    notes: str
    updated_at: datetime
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/wishlist/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/wishlist/models.py tests/wishlist/test_models.py
git commit -m "wishlist: PlantSelector, WishlistRow, Wishlist dataclasses"
```

---

## Task 6: `fits_constraint` predicate

**Files:**
- Modify: `src/wishlist/sizes.py`
- Modify: `tests/wishlist/test_sizes.py`

- [ ] **Step 1: Write failing tests for `fits_constraint`**

Add at the end of `tests/wishlist/test_sizes.py`:

```python
from dataclasses import dataclass
from datetime import datetime

from src.wishlist.models import PlantSelector, WishlistRow
from src.wishlist.sizes import fits_constraint


@dataclass
class FakeProduct:
    """Minimal product shape consumed by fits_constraint."""

    size_kind: str
    pot_size_litres: float | None


def _row(min_litres: float | None, allow_bare_root: bool) -> WishlistRow:
    sel = PlantSelector("species", "Test", "test", None, None, "Test")
    return WishlistRow(
        id="t",
        selector=sel,
        qty=1,
        min_litres=min_litres,
        allow_bare_root=allow_bare_root,
        added_at=datetime(2026, 5, 13),
    )


def test_potted_no_min_litres_passes():
    p = FakeProduct(size_kind="potted", pot_size_litres=2.0)
    assert fits_constraint(p, _row(None, True)) is True
    assert fits_constraint(p, _row(None, False)) is True


def test_potted_with_min_litres_at_threshold_passes():
    p = FakeProduct(size_kind="potted", pot_size_litres=3.0)
    assert fits_constraint(p, _row(3.0, False)) is True


def test_potted_with_min_litres_below_threshold_fails():
    p = FakeProduct(size_kind="potted", pot_size_litres=2.0)
    assert fits_constraint(p, _row(3.0, True)) is False


def test_potted_with_null_litres_and_min_constraint_fails():
    p = FakeProduct(size_kind="potted", pot_size_litres=None)
    assert fits_constraint(p, _row(3.0, True)) is False


def test_bare_root_passes_when_allowed():
    p = FakeProduct(size_kind="bare_root", pot_size_litres=None)
    assert fits_constraint(p, _row(None, True)) is True


def test_bare_root_rejects_when_disallowed():
    p = FakeProduct(size_kind="bare_root", pot_size_litres=None)
    assert fits_constraint(p, _row(None, False)) is False


def test_rootball_behaves_like_bare_root():
    p = FakeProduct(size_kind="rootball", pot_size_litres=None)
    assert fits_constraint(p, _row(None, True)) is True
    assert fits_constraint(p, _row(None, False)) is False


def test_unknown_only_passes_permissive_rows():
    p = FakeProduct(size_kind="unknown", pot_size_litres=None)
    # Permissive: no min litres AND bare-root allowed.
    assert fits_constraint(p, _row(None, True)) is True
    # Any constraint -> reject.
    assert fits_constraint(p, _row(1.0, True)) is False
    assert fits_constraint(p, _row(None, False)) is False


def test_non_plant_always_fails():
    p = FakeProduct(size_kind="non_plant", pot_size_litres=None)
    assert fits_constraint(p, _row(None, True)) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/wishlist/test_sizes.py -v -k fits_constraint`
Expected: FAIL — `fits_constraint` not importable.

- [ ] **Step 3: Add `fits_constraint` to `src/wishlist/sizes.py`**

Append to `src/wishlist/sizes.py`:

```python
# --- Constraint matching ------------------------------------------------------

from typing import Protocol

from src.wishlist.models import WishlistRow


class _SizedProduct(Protocol):
    """The minimal product shape consumed by ``fits_constraint``.

    Real products are polars rows; the protocol keeps this function
    decoupled and lets tests use simple dataclasses.
    """

    size_kind: str
    pot_size_litres: float | None


def fits_constraint(product: _SizedProduct, row: WishlistRow) -> bool:
    """Return True if ``product`` satisfies the wishlist row's size constraint.

    See spec §5.5. Decision table:

    | size_kind  | min_litres   | allow_bare_root | result                      |
    |------------|--------------|-----------------|-----------------------------|
    | potted     | None         | any             | True                        |
    | potted     | n            | any             | product.litres >= n         |
    | bare_root  | any          | True            | True                        |
    | bare_root  | any          | False           | False                       |
    | rootball   | (same as bare_root)                                          |
    | unknown    | None         | True            | True                        |
    | unknown    | n OR False   | ...             | False                       |
    | non_plant  | any          | any             | False                       |
    """

    if product.size_kind == "potted":
        if row.min_litres is None:
            return True
        if product.pot_size_litres is None:
            return False
        return product.pot_size_litres >= row.min_litres
    if product.size_kind in ("bare_root", "rootball"):
        return row.allow_bare_root
    if product.size_kind == "unknown":
        return row.min_litres is None and row.allow_bare_root
    # non_plant
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/wishlist/test_sizes.py -v`
Expected: PASS (all tests, including the new `fits_constraint` ones).

- [ ] **Step 5: Commit**

```bash
git add src/wishlist/sizes.py tests/wishlist/test_sizes.py
git commit -m "wishlist: fits_constraint predicate"
```

---

## Task 7: Wishlist persistence (JSON, atomic write)

**Files:**
- Create: `src/wishlist/state.py`
- Create: `tests/wishlist/test_state.py`

- [ ] **Step 1: Write failing tests for state**

Create `tests/wishlist/test_state.py`:

```python
"""Tests for wishlist JSON persistence."""

from datetime import datetime

import pytest

from src.wishlist.models import PlantSelector, Wishlist, WishlistRow
from src.wishlist.state import load_wishlist, save_wishlist


def _sample_wishlist() -> Wishlist:
    sel = PlantSelector(
        kind="cultivar",
        genus="Acer",
        species="palmatum",
        cultivar="Bloodgood",
        category=None,
        label="Acer palmatum 'Bloodgood'",
    )
    row = WishlistRow(
        id="abc-123",
        selector=sel,
        qty=2,
        min_litres=3.0,
        allow_bare_root=False,
        added_at=datetime(2026, 5, 13, 12, 0, 0),
    )
    return Wishlist(rows=[row], notes="Test", updated_at=datetime(2026, 5, 13, 12, 0, 0))


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "wishlist.json"
    wl = _sample_wishlist()
    save_wishlist(wl, path=path)
    loaded = load_wishlist(path=path)
    assert loaded == wl


def test_load_missing_file_returns_empty(tmp_path):
    path = tmp_path / "does_not_exist.json"
    loaded = load_wishlist(path=path)
    assert loaded.rows == []
    assert loaded.notes == ""


def test_atomic_write_uses_tmp_file(tmp_path):
    path = tmp_path / "wishlist.json"
    tmp = tmp_path / "wishlist.json.tmp"
    wl = _sample_wishlist()
    save_wishlist(wl, path=path)
    # After save, the .tmp file should not exist (renamed away).
    assert path.exists()
    assert not tmp.exists()


def test_load_falls_back_to_tmp_when_main_missing(tmp_path):
    path = tmp_path / "wishlist.json"
    tmp = tmp_path / "wishlist.json.tmp"
    # Simulate a crash mid-save: only the .tmp file exists.
    wl = _sample_wishlist()
    save_wishlist(wl, path=tmp)  # writes wishlist.json.tmp.tmp then renames -> wishlist.json.tmp
    assert tmp.exists()
    loaded = load_wishlist(path=path)
    assert loaded == wl


def test_load_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "wishlist.json"
    path.write_text("not valid json {{{")
    loaded = load_wishlist(path=path)
    assert loaded.rows == []


def test_wishlist_with_null_min_litres_roundtrips(tmp_path):
    path = tmp_path / "wishlist.json"
    sel = PlantSelector("genus", "Rosa", None, None, None, "Rosa (any)")
    row = WishlistRow("id1", sel, 5, None, True, datetime(2026, 5, 13))
    wl = Wishlist(rows=[row], notes="", updated_at=datetime(2026, 5, 13))
    save_wishlist(wl, path=path)
    loaded = load_wishlist(path=path)
    assert loaded.rows[0].min_litres is None
    assert loaded == wl
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/wishlist/test_state.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/wishlist/state.py`**

```python
"""Load and save the active wishlist as JSON.

Atomic-write pattern: write to ``<path>.tmp``, fsync, then rename over
the destination. ``load_wishlist`` falls back to the ``.tmp`` file if
the main file is missing (i.e. a crash interrupted the rename).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.wishlist.models import PlantSelector, Wishlist, WishlistRow

DEFAULT_PATH = Path(__file__).resolve().parents[2] / ".wishlist.json"


def _wishlist_to_dict(wl: Wishlist) -> dict:
    """Convert a Wishlist to a JSON-serialisable dict (datetimes as ISO strings)."""

    return {
        "rows": [
            {
                "id": r.id,
                "selector": asdict(r.selector),
                "qty": r.qty,
                "min_litres": r.min_litres,
                "allow_bare_root": r.allow_bare_root,
                "added_at": r.added_at.isoformat(),
            }
            for r in wl.rows
        ],
        "notes": wl.notes,
        "updated_at": wl.updated_at.isoformat(),
    }


def _wishlist_from_dict(data: dict) -> Wishlist:
    rows = [
        WishlistRow(
            id=r["id"],
            selector=PlantSelector(**r["selector"]),
            qty=r["qty"],
            min_litres=r["min_litres"],
            allow_bare_root=r["allow_bare_root"],
            added_at=datetime.fromisoformat(r["added_at"]),
        )
        for r in data.get("rows", [])
    ]
    return Wishlist(
        rows=rows,
        notes=data.get("notes", ""),
        updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
    )


def save_wishlist(wl: Wishlist, *, path: Path | None = None) -> None:
    """Atomically write the wishlist to ``path`` (defaults to project root)."""

    dest = path or DEFAULT_PATH
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    payload = json.dumps(_wishlist_to_dict(wl), indent=2)

    with tmp.open("w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dest)


def _empty() -> Wishlist:
    return Wishlist(rows=[], notes="", updated_at=datetime.now())


def load_wishlist(*, path: Path | None = None) -> Wishlist:
    """Load the wishlist. Returns empty on any failure (missing/corrupt)."""

    dest = path or DEFAULT_PATH
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    for candidate in (dest, tmp):
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            return _wishlist_from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    return _empty()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/wishlist/test_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/wishlist/state.py tests/wishlist/test_state.py
git commit -m "wishlist: JSON persistence with atomic write + tmp fallback"
```

---

## Task 8: Candidate resolution (PlantSelector → products + autocomplete options)

**Files:**
- Create: `src/wishlist/candidates.py`
- Create: `tests/wishlist/test_candidates.py`
- Create: `tests/wishlist/conftest.py`

- [ ] **Step 1: Create a shared pytest fixture for a mini products parquet**

Create `tests/wishlist/conftest.py`:

```python
"""Shared fixtures for wishlist tests — synthetic products + nurseries."""

from datetime import date

import polars as pl
import pytest


@pytest.fixture
def mini_products() -> pl.DataFrame:
    """A small in-memory products_matched DataFrame.

    Five plants across four nurseries, with mixed size_kinds, currencies,
    and stock states. Designed to exercise the predicate, optimiser, and
    candidate-resolution paths.
    """
    return pl.DataFrame({
        "source": [
            "tullys", "tullys", "tullys",
            "hedgingie", "hedgingie",
            "famous_roses",
            "newlands", "newlands",
        ],
        "product_name_clean": [
            "Acer palmatum Bloodgood", "Acer palmatum Atropurpureum", "Rosa Gertrude Jekyll",
            "Acer palmatum Bloodgood", "Lavandula angustifolia Hidcote",
            "Rosa Gertrude Jekyll",
            "Acer palmatum Bloodgood", "Carpinus betulus",
        ],
        "genus":       ["Acer", "Acer", "Rosa", "Acer", "Lavandula", "Rosa", "Acer", "Carpinus"],
        "species":     ["palmatum", "palmatum", None, "palmatum", "angustifolia", None, "palmatum", "betulus"],
        "cultivar":    ["Bloodgood", "Atropurpureum", "Gertrude Jekyll", "Bloodgood", "Hidcote", "Gertrude Jekyll", "Bloodgood", None],
        "size":        ["3 Litre", "3 Litre", "5 Litre", "2 Litre", "1 Litre", "Bare Root", "5 Litre", "10 Litre"],
        "size_kind":   ["potted", "potted", "potted", "potted", "potted", "bare_root", "potted", "potted"],
        "pot_size_litres": [3.0, 3.0, 5.0, 2.0, 1.0, None, 5.0, 10.0],
        "price":       [22.50, 19.80, 24.00, 18.00, 6.50, 14.00, 26.00, 15.50],
        "currency":    ["EUR", "EUR", "EUR", "EUR", "EUR", "EUR", "EUR", "EUR"],
        "stock":       ["5", "3", "10", "20", "30", None, "4", "100"],
        "quantity":    [1, 1, 1, 1, 1, 1, 1, 1],
        "is_plant":    [True, True, True, True, True, True, True, True],
        "product_category": ["plant", "plant", "plant", "plant", "plant", "plant", "plant", "plant"],
        "product_url": [
            "https://shop.tullynurseries.ie/acer-bloodgood",
            "https://shop.tullynurseries.ie/acer-atropurpureum",
            "https://shop.tullynurseries.ie/rosa-gertrude",
            "https://hedging.ie/acer-bloodgood",
            "https://hedging.ie/lavandula-hidcote",
            "https://en.famousroses.eu/rosa-gertrude",
            "https://www.newlands.ie/acer-bloodgood",
            "https://www.newlands.ie/carpinus",
        ],
        "input_date": [date(2026, 5, 1)] * 8,
    })
```

- [ ] **Step 2: Write failing tests for candidates**

Create `tests/wishlist/test_candidates.py`:

```python
"""Tests for PlantSelector resolution + autocomplete option construction."""

from datetime import datetime

from src.wishlist.candidates import (
    AutocompleteOption,
    build_autocomplete_options,
    resolve_candidates,
)
from src.wishlist.models import PlantSelector, WishlistRow


def _row(sel: PlantSelector, *, min_litres=None, allow_bare_root=True) -> WishlistRow:
    return WishlistRow(
        id="r",
        selector=sel,
        qty=1,
        min_litres=min_litres,
        allow_bare_root=allow_bare_root,
        added_at=datetime(2026, 5, 13),
    )


def test_resolve_cultivar_level(mini_products):
    sel = PlantSelector("cultivar", "Acer", "palmatum", "Bloodgood", None, "Acer p. 'Bloodgood'")
    out = resolve_candidates(_row(sel), mini_products)
    # Three rows match cultivar (tullys, hedgingie, newlands)
    assert len(out) == 3
    assert set(out["source"].to_list()) == {"tullys", "hedgingie", "newlands"}


def test_resolve_species_level(mini_products):
    sel = PlantSelector("species", "Acer", "palmatum", None, None, "Acer palmatum (any)")
    out = resolve_candidates(_row(sel), mini_products)
    # Bloodgood + Atropurpureum across nurseries = 4 rows
    assert len(out) == 4


def test_resolve_genus_level(mini_products):
    sel = PlantSelector("genus", "Acer", None, None, None, "Acer (any)")
    out = resolve_candidates(_row(sel), mini_products)
    assert len(out) == 4  # only A. palmatum in fixture, but all match genus


def test_min_litres_filters_out_smaller(mini_products):
    sel = PlantSelector("cultivar", "Acer", "palmatum", "Bloodgood", None, "Acer p. 'Bloodgood'")
    out = resolve_candidates(_row(sel, min_litres=4.0), mini_products)
    # 5L from newlands only; 3L (tullys) and 2L (hedgingie) excluded
    assert len(out) == 1
    assert out["source"].to_list() == ["newlands"]


def test_disallow_bare_root_filters_out(mini_products):
    sel = PlantSelector("cultivar", "Rosa", None, "Gertrude Jekyll", None, "Rosa 'Gertrude J.'")
    out = resolve_candidates(_row(sel, allow_bare_root=False), mini_products)
    # famous_roses has bare-root only; should be filtered
    assert "famous_roses" not in out["source"].to_list()


def test_low_stock_filters_out(mini_products):
    sel = PlantSelector("cultivar", "Acer", "palmatum", "Bloodgood", None, "Acer p. 'Bloodgood'")
    # Asking for qty=10 but tullys has stock=5, hedgingie stock=20, newlands stock=4
    row = WishlistRow("r", sel, qty=10, min_litres=None, allow_bare_root=True, added_at=datetime(2026, 5, 13))
    out = resolve_candidates(row, mini_products)
    # Only hedgingie (stock 20) survives
    assert out["source"].to_list() == ["hedgingie"]


def test_null_stock_treated_as_available(mini_products):
    sel = PlantSelector("cultivar", "Rosa", None, "Gertrude Jekyll", None, "Rosa 'Gertrude J.'")
    # famous_roses has stock=None — should be kept under high-qty too
    row = WishlistRow("r", sel, qty=99, min_litres=None, allow_bare_root=True, added_at=datetime(2026, 5, 13))
    out = resolve_candidates(row, mini_products)
    assert "famous_roses" in out["source"].to_list()


def test_autocomplete_options_include_all_granularities(mini_products):
    opts = build_autocomplete_options(mini_products)
    kinds = {o.selector.kind for o in opts}
    assert "cultivar" in kinds
    assert "species" in kinds
    assert "genus" in kinds


def test_autocomplete_options_have_nursery_counts(mini_products):
    opts = build_autocomplete_options(mini_products)
    # Find the Bloodgood cultivar entry — should report 3 nurseries
    bloodgood = next(o for o in opts if o.selector.kind == "cultivar" and o.selector.cultivar == "Bloodgood")
    assert bloodgood.nursery_count == 3
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/wishlist/test_candidates.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `src/wishlist/candidates.py`**

```python
"""Resolve a wishlist row to its candidate products + build autocomplete options.

The candidate-resolution path filters ``products_matched`` by the row's
PlantSelector and size constraints. The autocomplete-options path
produces the searchable list shown in the Build tab.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from src.wishlist.models import PlantSelector, WishlistRow
from src.wishlist.sizes import fits_constraint


# --- Candidate resolution -----------------------------------------------------


def _parse_stock(s: str | None) -> int | None:
    """Parse the products_matched.stock string into an int, or None if unparsable."""
    if s is None or s == "":
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def resolve_candidates(row: WishlistRow, products: pl.DataFrame) -> pl.DataFrame:
    """Filter ``products`` to those that satisfy this wishlist row.

    Applies, in order:
      - is_plant = True
      - PlantSelector match (one of cultivar / species / genus / category)
      - fits_constraint (size_kind + min_litres + allow_bare_root)
      - stock filter: known stock < row.qty -> drop; null stock -> keep
    """

    df = products.filter(pl.col("is_plant"))

    sel = row.selector
    if sel.kind == "cultivar":
        df = df.filter(
            (pl.col("genus") == sel.genus)
            & (pl.col("species") == sel.species)
            & (pl.col("cultivar") == sel.cultivar)
        )
    elif sel.kind == "species":
        df = df.filter((pl.col("genus") == sel.genus) & (pl.col("species") == sel.species))
    elif sel.kind == "genus":
        df = df.filter(pl.col("genus") == sel.genus)
    elif sel.kind == "category":
        df = df.filter(pl.col("product_category") == sel.category)
    else:
        return df.head(0)

    if len(df) == 0:
        return df

    # Apply fits_constraint row-by-row. polars filter on a Python callable
    # via map_elements; for small fixtures and realistic wishlists this is
    # fast enough.
    keep_mask = [
        fits_constraint(_RowProxy(sk, l), row)
        for sk, l in zip(df["size_kind"].to_list(), df["pot_size_litres"].to_list())
    ]
    df = df.filter(pl.Series(keep_mask))

    # Stock filter.
    if len(df) == 0:
        return df
    stocks = [_parse_stock(s) for s in df["stock"].to_list()]
    stock_ok = [s is None or s >= row.qty for s in stocks]
    return df.filter(pl.Series(stock_ok))


class _RowProxy:
    """Tiny shim so fits_constraint can be called with non-polars objects."""

    __slots__ = ("size_kind", "pot_size_litres")

    def __init__(self, size_kind: str, pot_size_litres: float | None):
        self.size_kind = size_kind
        self.pot_size_litres = pot_size_litres


# --- Autocomplete option construction -----------------------------------------


@dataclass
class AutocompleteOption:
    """One row in the Build-tab autocomplete dropdown."""

    selector: PlantSelector
    nursery_count: int


def build_autocomplete_options(products: pl.DataFrame) -> list[AutocompleteOption]:
    """Build the searchable options list shown in the Build tab.

    Returns all distinct (genus, species, cultivar) cultivar entries,
    plus species-level "any cultivar" entries, plus genus-level "any"
    entries, plus a small fixed set of category entries.
    """

    plants = products.filter(pl.col("is_plant") & pl.col("genus").is_not_null())
    options: list[AutocompleteOption] = []

    # Cultivar-level — one row per (genus, species, cultivar) where cultivar is not null.
    cultivars = (
        plants.filter(pl.col("cultivar").is_not_null())
        .group_by(["genus", "species", "cultivar"])
        .agg(pl.col("source").n_unique().alias("n"))
    )
    for g, s, c, n in zip(cultivars["genus"], cultivars["species"], cultivars["cultivar"], cultivars["n"]):
        label = f"{g} {s} '{c}'" if s else f"{g} '{c}'"
        options.append(AutocompleteOption(
            selector=PlantSelector("cultivar", g, s, c, None, label),
            nursery_count=int(n),
        ))

    # Species-level — "any cultivar" for each (genus, species) with > 1 cultivar.
    species = plants.group_by(["genus", "species"]).agg(pl.col("source").n_unique().alias("n"))
    for g, s, n in zip(species["genus"], species["species"], species["n"]):
        if s is None:
            continue
        label = f"{g} {s} (any cultivar)"
        options.append(AutocompleteOption(
            selector=PlantSelector("species", g, s, None, None, label),
            nursery_count=int(n),
        ))

    # Genus-level — "any species" for each genus.
    genera = plants.group_by("genus").agg(pl.col("source").n_unique().alias("n"))
    for g, n in zip(genera["genus"], genera["n"]):
        label = f"{g} (any species)"
        options.append(AutocompleteOption(
            selector=PlantSelector("genus", g, None, None, None, label),
            nursery_count=int(n),
        ))

    # Fixed categories — present only if any matching products exist.
    fixed_categories = {
        "hedging_mix": "[Hedging mix]",
        "wildflower_mix": "[Native wildflower mix]",
        "bulb_mixed": "[Bulb mixed]",
    }
    for cat, label in fixed_categories.items():
        n = products.filter(pl.col("product_category") == cat).select(pl.col("source").n_unique()).item()
        if n and n > 0:
            options.append(AutocompleteOption(
                selector=PlantSelector("category", None, None, None, cat, label),
                nursery_count=int(n),
            ))

    return options
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/wishlist/test_candidates.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/wishlist/candidates.py tests/wishlist/test_candidates.py tests/wishlist/conftest.py
git commit -m "wishlist: candidate resolution + autocomplete options"
```

---

## Task 9: Shipping calculation

**Files:**
- Create: `src/wishlist/shipping.py`
- Create: `tests/wishlist/test_shipping.py`

- [ ] **Step 1: Write failing tests for shipping**

Create `tests/wishlist/test_shipping.py`:

```python
"""Tests for shipping calculation across all delivery types."""

import pytest

from src.common.nurseries import DeliveryFee, NurseryConfig
from src.wishlist.shipping import compute_shipping


def _cfg(delivery_type, fees=None, min_order=0.0, per_box=None, **overrides):
    return NurseryConfig(
        display_name="Test",
        base_url="https://example.com",
        currency="EUR",
        vat_included=True,
        delivery_type=delivery_type,
        delivery_fees=fees or [],
        delivery_per_box_eur=per_box,
        min_order_eur=min_order,
        **overrides,
    )


# --- free ----------------------------------------------------------------


def test_free_returns_zero():
    cfg = _cfg("free")
    assert compute_shipping(100.0, cfg) == 0.0


# --- flat ----------------------------------------------------------------


def test_flat_returns_single_fee():
    cfg = _cfg("flat", fees=[DeliveryFee(max_value_eur=None, fee_eur=6.95)])
    assert compute_shipping(50.0, cfg) == 6.95


def test_flat_returns_same_fee_for_any_subtotal():
    cfg = _cfg("flat", fees=[DeliveryFee(max_value_eur=None, fee_eur=9.95)])
    assert compute_shipping(10.0, cfg) == 9.95
    assert compute_shipping(1000.0, cfg) == 9.95


# --- tiered --------------------------------------------------------------


def test_tiered_picks_first_bucket_below_subtotal():
    cfg = _cfg("tiered", fees=[
        DeliveryFee(max_value_eur=600, fee_eur=60),
        DeliveryFee(max_value_eur=None, fee_eur=0),
    ])
    assert compute_shipping(500.0, cfg) == 60.0
    assert compute_shipping(700.0, cfg) == 0.0
    # At the boundary — first bucket includes its ceiling.
    assert compute_shipping(600.0, cfg) == 60.0


def test_tiered_falls_through_when_no_ceiling_tier():
    cfg = _cfg("tiered", fees=[DeliveryFee(max_value_eur=100, fee_eur=12.0)])
    # Subtotal exceeds the only ceiling — fall through to the highest fee.
    assert compute_shipping(500.0, cfg) == 12.0


def test_tiered_multi_bucket():
    cfg = _cfg("tiered", fees=[
        DeliveryFee(max_value_eur=50, fee_eur=15),
        DeliveryFee(max_value_eur=200, fee_eur=10),
        DeliveryFee(max_value_eur=None, fee_eur=0),
    ])
    assert compute_shipping(30.0, cfg) == 15
    assert compute_shipping(100.0, cfg) == 10
    assert compute_shipping(500.0, cfg) == 0


# --- per_box -------------------------------------------------------------


def test_per_box_returns_single_box_rate():
    cfg = _cfg("per_box", per_box=21.50)
    assert compute_shipping(600.0, cfg) == 21.50


# --- min_order -----------------------------------------------------------


def test_min_order_failure_returns_none():
    cfg = _cfg("flat", fees=[DeliveryFee(max_value_eur=None, fee_eur=5)], min_order=25)
    assert compute_shipping(20.0, cfg) is None


def test_min_order_exact_passes():
    cfg = _cfg("flat", fees=[DeliveryFee(max_value_eur=None, fee_eur=5)], min_order=25)
    assert compute_shipping(25.0, cfg) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/wishlist/test_shipping.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/wishlist/shipping.py`**

```python
"""Compute shipping cost for one nursery basket.

Reads the nursery config (from ``src/common/nurseries.py``) and dispatches
on ``delivery_type``. Enforces ``min_order_eur`` as a hard cutoff.
"""

from __future__ import annotations

from src.common.nurseries import NurseryConfig


def compute_shipping(basket_subtotal_eur: float, nursery: NurseryConfig) -> float | None:
    """Return shipping cost in EUR, or ``None`` if the basket fails ``min_order``.

    ``None`` is the signal to the optimiser to drop the subset.
    """

    if basket_subtotal_eur < nursery.min_order_eur:
        return None

    dt = nursery.delivery_type

    if dt == "free":
        return 0.0

    if dt == "flat":
        if not nursery.delivery_fees:
            return 0.0
        return float(nursery.delivery_fees[0].fee_eur)

    if dt == "tiered":
        if not nursery.delivery_fees:
            return 0.0
        # Sort buckets by ceiling asc; None ceiling sorts last.
        sorted_fees = sorted(
            nursery.delivery_fees,
            key=lambda f: float("inf") if f.max_value_eur is None else f.max_value_eur,
        )
        for f in sorted_fees:
            ceiling = float("inf") if f.max_value_eur is None else f.max_value_eur
            if basket_subtotal_eur <= ceiling:
                return float(f.fee_eur)
        # No tier matched (shouldn't happen if there's a None-ceiling bucket).
        return float(sorted_fees[-1].fee_eur)

    if dt == "per_box":
        return float(nursery.delivery_per_box_eur or 0.0)

    # by_weight, quote_only and any other type fall through to 0 with a
    # best-effort warning; surfaced in basket-card UI later.
    return 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/wishlist/test_shipping.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/wishlist/shipping.py tests/wishlist/test_shipping.py
git commit -m "wishlist: shipping calculation per delivery_type"
```

---

## Task 10: Optimiser engine

**Files:**
- Create: `src/wishlist/optimizer.py`
- Create: `tests/wishlist/test_optimizer.py`

- [ ] **Step 1: Write failing tests for the optimiser**

Create `tests/wishlist/test_optimizer.py`:

```python
"""Tests for the optimiser — small fixtures with known optima."""

from datetime import date, datetime

import polars as pl
import pytest

from src.common.nurseries import DeliveryFee, NurseryConfig
from src.wishlist.models import PlantSelector, Wishlist, WishlistRow
from src.wishlist.optimizer import optimise


def _row(sel_kind, genus, species=None, cultivar=None, qty=1, min_litres=None, allow_br=True):
    sel = PlantSelector(sel_kind, genus, species, cultivar, None, f"{genus} {species or ''} {cultivar or ''}".strip())
    return WishlistRow(
        id=f"r-{genus}-{cultivar or species or ''}",
        selector=sel,
        qty=qty,
        min_litres=min_litres,
        allow_bare_root=allow_br,
        added_at=datetime(2026, 5, 13),
    )


def _nursery(name, delivery_type, fees=None, min_order=0.0, per_box=None, currency="EUR", vat_included=True):
    return NurseryConfig(
        display_name=name,
        base_url="https://example.com",
        currency=currency,
        vat_included=vat_included,
        delivery_type=delivery_type,
        delivery_fees=fees or [],
        delivery_per_box_eur=per_box,
        min_order_eur=min_order,
    )


# --- Fixture: 2 plants, 3 nurseries ---


@pytest.fixture
def two_plant_three_nursery():
    products = pl.DataFrame({
        "source":              ["a", "a", "b", "c"],
        "genus":               ["Acer", "Rosa", "Acer", "Acer"],
        "species":             ["palmatum", None, "palmatum", "palmatum"],
        "cultivar":            ["Bloodgood", "Gertrude", "Bloodgood", "Bloodgood"],
        "size":                ["3 Litre"] * 4,
        "size_kind":           ["potted"] * 4,
        "pot_size_litres":     [3.0] * 4,
        "price":               [20.0, 15.0, 18.0, 22.0],
        "currency":            ["EUR"] * 4,
        "stock":               ["10"] * 4,
        "quantity":            [1] * 4,
        "is_plant":            [True] * 4,
        "product_category":    ["plant"] * 4,
        "product_name_clean":  ["x"] * 4,
        "product_url":         ["https://x"] * 4,
        "input_date":          [date(2026, 5, 1)] * 4,
    })
    nurseries = {
        "a": _nursery("Alpha", "flat", fees=[DeliveryFee(max_value_eur=None, fee_eur=5.0)]),
        "b": _nursery("Beta",  "flat", fees=[DeliveryFee(max_value_eur=None, fee_eur=10.0)]),
        "c": _nursery("Gamma", "free"),
    }
    return products, nurseries


def test_single_nursery_chosen_when_one_has_everything(two_plant_three_nursery):
    products, nurseries = two_plant_three_nursery
    wl = Wishlist(rows=[
        _row("cultivar", "Acer", "palmatum", "Bloodgood"),
        _row("cultivar", "Rosa", None, "Gertrude"),
    ], notes="", updated_at=datetime(2026, 5, 13))

    plans = optimise(wl, products, nurseries)
    # Best plan should use nursery "a" alone — has both, only fee €5.
    best = min(plans, key=lambda p: p.total_eur)
    assert len(best.baskets) == 1
    assert next(iter(best.baskets.keys())) == "a"
    assert best.total_eur == 20.0 + 15.0 + 5.0


def test_optimiser_returns_per_max_nurseries_plan(two_plant_three_nursery):
    products, nurseries = two_plant_three_nursery
    wl = Wishlist(rows=[
        _row("cultivar", "Acer", "palmatum", "Bloodgood"),
    ], notes="", updated_at=datetime(2026, 5, 13))

    plans = optimise(wl, products, nurseries)
    # Cheapest single-row plan: nursery "b" at price €18 + €10 ship = €28.
    # Nursery "a": €20 + €5 = €25.
    # Nursery "c": €22 + €0 = €22  <- best
    best = min(plans, key=lambda p: p.total_eur)
    assert next(iter(best.baskets.keys())) == "c"
    assert best.total_eur == 22.0


# --- Tiered free-over-X dominates ---


def test_tiered_free_over_threshold_can_dominate():
    products = pl.DataFrame({
        "source":           ["tully", "cheap", "cheap"],
        "genus":            ["Acer", "Acer", "Rosa"],
        "species":          ["palmatum", "palmatum", None],
        "cultivar":         ["Bloodgood", "Bloodgood", "Gertrude"],
        "size":             ["3 Litre"] * 3,
        "size_kind":        ["potted"] * 3,
        "pot_size_litres":  [3.0] * 3,
        # Tully's is dearer per-plant but tipping over the free-shipping
        # threshold can still win in a multi-row order.
        "price":            [620.0, 100.0, 50.0],
        "currency":         ["EUR"] * 3,
        "stock":            ["10"] * 3,
        "quantity":         [1] * 3,
        "is_plant":         [True] * 3,
        "product_category": ["plant"] * 3,
        "product_name_clean": ["x"] * 3,
        "product_url":      ["https://x"] * 3,
        "input_date":       [date(2026, 5, 1)] * 3,
    })
    nurseries = {
        "tully": NurseryConfig(
            display_name="Tully", base_url="https://example.com", currency="EUR", vat_included=True,
            delivery_type="tiered",
            delivery_fees=[
                DeliveryFee(max_value_eur=600, fee_eur=60),
                DeliveryFee(max_value_eur=None, fee_eur=0),
            ],
            min_order_eur=0,
        ),
        "cheap": NurseryConfig(
            display_name="Cheap", base_url="https://example.com", currency="EUR", vat_included=True,
            delivery_type="flat",
            delivery_fees=[DeliveryFee(max_value_eur=None, fee_eur=10)],
            min_order_eur=0,
        ),
    }
    wl = Wishlist(rows=[_row("cultivar", "Acer", "palmatum", "Bloodgood")],
                  notes="", updated_at=datetime(2026, 5, 13))
    plans = optimise(wl, products, nurseries)
    best_single = min((p for p in plans if len(p.baskets) == 1), key=lambda p: p.total_eur)
    # "cheap" should win for a single-Acer order (€100 + €10 = €110 vs €620 + €60 = €680).
    assert "cheap" in best_single.baskets


# --- min_order infeasibility ---


def test_min_order_makes_a_nursery_infeasible():
    products = pl.DataFrame({
        "source":           ["a", "b"],
        "genus":            ["Acer", "Acer"],
        "species":          ["palmatum", "palmatum"],
        "cultivar":         ["Bloodgood", "Bloodgood"],
        "size":             ["3 Litre", "3 Litre"],
        "size_kind":        ["potted", "potted"],
        "pot_size_litres":  [3.0, 3.0],
        "price":            [10.0, 25.0],
        "currency":         ["EUR", "EUR"],
        "stock":            ["10", "10"],
        "quantity":         [1, 1],
        "is_plant":         [True, True],
        "product_category": ["plant", "plant"],
        "product_name_clean": ["x", "x"],
        "product_url":      ["https://x", "https://x"],
        "input_date":       [date(2026, 5, 1), date(2026, 5, 1)],
    })
    nurseries = {
        "a": NurseryConfig(
            display_name="A", base_url="https://example.com", currency="EUR", vat_included=True,
            delivery_type="flat",
            delivery_fees=[DeliveryFee(max_value_eur=None, fee_eur=5)],
            min_order_eur=100,  # below this: infeasible
        ),
        "b": NurseryConfig(
            display_name="B", base_url="https://example.com", currency="EUR", vat_included=True,
            delivery_type="flat",
            delivery_fees=[DeliveryFee(max_value_eur=None, fee_eur=5)],
            min_order_eur=0,
        ),
    }
    wl = Wishlist(rows=[_row("cultivar", "Acer", "palmatum", "Bloodgood", qty=1)],
                  notes="", updated_at=datetime(2026, 5, 13))
    plans = optimise(wl, products, nurseries)
    # No plan should select nursery "a" (its subtotal of €10 is below its min_order of €100)
    for p in plans:
        assert "a" not in p.baskets


# --- VAT uplift ---


def test_vat_uplift_applies_to_non_vat_included_nurseries():
    products = pl.DataFrame({
        "source":           ["exvat", "incvat"],
        "genus":            ["Acer", "Acer"],
        "species":          ["palmatum", "palmatum"],
        "cultivar":         ["Bloodgood", "Bloodgood"],
        "size":             ["3 Litre", "3 Litre"],
        "size_kind":        ["potted", "potted"],
        "pot_size_litres":  [3.0, 3.0],
        # ex-VAT 20 * 1.23 = 24.60 vs inc-VAT 23 -> inc-VAT should win.
        "price":            [20.0, 23.0],
        "currency":         ["EUR", "EUR"],
        "stock":            ["10", "10"],
        "quantity":         [1, 1],
        "is_plant":         [True, True],
        "product_category": ["plant", "plant"],
        "product_name_clean": ["x", "x"],
        "product_url":      ["https://x", "https://x"],
        "input_date":       [date(2026, 5, 1), date(2026, 5, 1)],
    })
    nurseries = {
        "exvat": NurseryConfig(
            display_name="ExVAT", base_url="https://example.com", currency="EUR",
            vat_included=False,
            delivery_type="free",
        ),
        "incvat": NurseryConfig(
            display_name="IncVAT", base_url="https://example.com", currency="EUR",
            vat_included=True,
            delivery_type="free",
        ),
    }
    wl = Wishlist(rows=[_row("cultivar", "Acer", "palmatum", "Bloodgood")],
                  notes="", updated_at=datetime(2026, 5, 13))
    plans = optimise(wl, products, nurseries)
    best = min(plans, key=lambda p: p.total_eur)
    assert "incvat" in best.baskets
    assert "exvat" not in best.baskets


# --- Performance ---


def test_perf_20_rows_15_candidate_nurseries():
    """Generate a synthetic 20-row wishlist resolving to ~15 nurseries; complete in < 1.5s."""
    import time

    nurseries_count = 15
    rows_count = 20
    sources = [f"n{i}" for i in range(nurseries_count)]

    rows = []
    prices = []
    sizes_kinds = []
    litres = []
    genera = []
    species = []
    cultivars = []
    is_plants = []
    cats = []
    names = []
    urls = []
    dates = []
    stocks = []
    qtys = []
    currencies = []
    source_col = []

    for i in range(rows_count):
        for j, n in enumerate(sources):
            source_col.append(n)
            genera.append(f"Genus{i}")
            species.append(f"species{i}")
            cultivars.append(f"Cv{i}")
            sizes_kinds.append("potted")
            litres.append(3.0)
            prices.append(10.0 + (i % 5) + (j % 4))
            currencies.append("EUR")
            stocks.append("99")
            qtys.append(1)
            is_plants.append(True)
            cats.append("plant")
            names.append(f"Plant{i}")
            urls.append("https://x")
            dates.append(date(2026, 5, 1))

    products = pl.DataFrame({
        "source": source_col,
        "genus": genera,
        "species": species,
        "cultivar": cultivars,
        "size": ["3 Litre"] * len(source_col),
        "size_kind": sizes_kinds,
        "pot_size_litres": litres,
        "price": prices,
        "currency": currencies,
        "stock": stocks,
        "quantity": qtys,
        "is_plant": is_plants,
        "product_category": cats,
        "product_name_clean": names,
        "product_url": urls,
        "input_date": dates,
    })

    nurseries = {
        n: NurseryConfig(
            display_name=n, base_url="https://example.com", currency="EUR", vat_included=True,
            delivery_type="flat",
            delivery_fees=[DeliveryFee(max_value_eur=None, fee_eur=5)],
        )
        for n in sources
    }

    wl_rows = [_row("cultivar", f"Genus{i}", f"species{i}", f"Cv{i}") for i in range(rows_count)]
    wl = Wishlist(rows=wl_rows, notes="", updated_at=datetime(2026, 5, 13))

    t0 = time.perf_counter()
    plans = optimise(wl, products, nurseries)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.5, f"Optimisation took {elapsed:.2f}s (limit 1.5s)"
    assert len(plans) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/wishlist/test_optimizer.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/wishlist/optimizer.py`**

```python
"""Wishlist optimiser — subset enumeration with shipping rules.

Pure function. ``optimise(wishlist, products, nurseries)`` returns a list
of feasible plans sorted by total EUR ascending. The UI picks among them
via a max-nurseries slider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import chain, combinations
from typing import Iterable

import polars as pl

from src.common.fx import FxRateMissing, to_eur
from src.common.nurseries import NurseryConfig
from src.wishlist.candidates import resolve_candidates
from src.wishlist.models import Wishlist, WishlistRow
from src.wishlist.shipping import compute_shipping

VAT_IRELAND = 0.23
MAX_SUBSET_SIZE = 8


@dataclass
class BasketLine:
    row_id: str
    product_name: str
    size: str
    qty: int
    unit_price_native: float
    currency: str
    unit_price_eur: float
    line_eur: float
    product_url: str
    nursery: str
    input_date: date | None       # for freshness badge in Plan UI


@dataclass
class Plan:
    baskets: dict[str, list[BasketLine]]        # nursery_id -> lines
    subtotals_eur: dict[str, float]
    shipping_eur: dict[str, float]
    total_eur: float
    unfulfilled_row_ids: list[str] = field(default_factory=list)


def _unit_price_eur(row, today: date) -> float | None:
    """EUR price for one unit, with VAT uplift if the nursery sells ex-VAT.

    Returns None if FX rate is missing.
    """
    try:
        eur = to_eur(float(row["price"]), row["currency"], on=today)
    except FxRateMissing:
        return None
    if not row["vat_included"]:
        eur = eur * (1.0 + VAT_IRELAND)
    return eur


def _cheapest_per_nursery(
    candidates: pl.DataFrame,
    nurseries: dict[str, NurseryConfig],
    today: date,
) -> dict[str, dict]:
    """For each nursery in candidates, return the single cheapest qualifying product."""

    if len(candidates) == 0:
        return {}

    rows = candidates.to_dicts()
    by_nursery: dict[str, dict] = {}
    for row in rows:
        nursery_id = row["source"]
        cfg = nurseries.get(nursery_id)
        if cfg is None:
            continue
        row["vat_included"] = cfg.vat_included
        eur = _unit_price_eur(row, today)
        if eur is None:
            continue
        row["unit_price_eur"] = eur
        prev = by_nursery.get(nursery_id)
        if prev is None or eur < prev["unit_price_eur"]:
            by_nursery[nursery_id] = row
    return by_nursery


def _subsets(items: Iterable[str], max_size: int) -> Iterable[tuple[str, ...]]:
    items = list(items)
    for r in range(1, min(len(items), max_size) + 1):
        yield from combinations(items, r)


def optimise(
    wishlist: Wishlist,
    products: pl.DataFrame,
    nurseries: dict[str, NurseryConfig],
    *,
    today: date | None = None,
) -> list[Plan]:
    """Return all feasible plans sorted by total_eur ascending.

    Each plan represents one valid nursery-subset assignment. The caller
    (typically the Plans tab UI) filters to ``len(baskets) <= max_nurseries``.
    """

    today = today or date.today()

    # Stage 1+2: build cheapest-per-nursery per wishlist row.
    cheapest_by_row: dict[str, dict[str, dict]] = {}
    for row in wishlist.rows:
        candidates = resolve_candidates(row, products)
        cheapest_by_row[row.id] = _cheapest_per_nursery(candidates, nurseries, today)

    candidate_nurseries: set[str] = set().union(
        *(set(c.keys()) for c in cheapest_by_row.values())
    )

    if not candidate_nurseries:
        return []

    plans: list[Plan] = []
    for subset in _subsets(candidate_nurseries, MAX_SUBSET_SIZE):
        plan = _build_plan(subset, cheapest_by_row, wishlist.rows, nurseries)
        if plan is not None:
            plans.append(plan)

    plans.sort(key=lambda p: p.total_eur)
    return plans


def _build_plan(
    subset: tuple[str, ...],
    cheapest_by_row: dict[str, dict[str, dict]],
    rows: list[WishlistRow],
    nurseries: dict[str, NurseryConfig],
) -> Plan | None:
    """Assemble a Plan for one subset. Returns None if any basket is infeasible."""

    baskets: dict[str, list[BasketLine]] = {n: [] for n in subset}
    unfulfilled: list[str] = []

    for row in rows:
        in_subset = {n: cheapest_by_row[row.id][n] for n in subset if n in cheapest_by_row[row.id]}
        if not in_subset:
            unfulfilled.append(row.id)
            continue
        chosen_nursery = min(in_subset, key=lambda n: in_subset[n]["unit_price_eur"])
        product = in_subset[chosen_nursery]
        line = BasketLine(
            row_id=row.id,
            product_name=product["product_name_clean"],
            size=product["size"],
            qty=row.qty,
            unit_price_native=float(product["price"]),
            currency=product["currency"],
            unit_price_eur=float(product["unit_price_eur"]),
            line_eur=float(product["unit_price_eur"]) * row.qty,
            product_url=product["product_url"],
            nursery=chosen_nursery,
            input_date=product.get("input_date"),
        )
        baskets[chosen_nursery].append(line)

    # Drop empty baskets.
    baskets = {n: lines for n, lines in baskets.items() if lines}

    subtotals: dict[str, float] = {}
    shipping: dict[str, float] = {}
    for nursery_id, lines in baskets.items():
        subtotal = sum(l.line_eur for l in lines)
        ship = compute_shipping(subtotal, nurseries[nursery_id])
        if ship is None:
            return None  # min_order failure -> infeasible subset
        subtotals[nursery_id] = subtotal
        shipping[nursery_id] = ship

    total = sum(subtotals.values()) + sum(shipping.values())
    return Plan(
        baskets=baskets,
        subtotals_eur=subtotals,
        shipping_eur=shipping,
        total_eur=total,
        unfulfilled_row_ids=unfulfilled,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/wishlist/test_optimizer.py -v`
Expected: PASS (all functional + performance < 1.5s).

- [ ] **Step 5: Commit**

```bash
git add src/wishlist/optimizer.py tests/wishlist/test_optimizer.py
git commit -m "wishlist: optimiser (subset enumeration, FX, VAT, min_order)"
```

---

## Task 11: Streamlit Build tab (autocomplete + wishlist editor + persistence)

**Files:**
- Create: `scripts/wishlist.py`
- Modify: `requirements.txt` (add streamlit)

- [ ] **Step 1: Add streamlit to requirements**

Edit `requirements.txt`. Add at the end:

```
streamlit
```

- [ ] **Step 2: Install streamlit**

```bash
.venv/Scripts/pip install streamlit
```

- [ ] **Step 3: Create `scripts/wishlist.py` with Build tab only**

```python
"""Blaithin wishlist optimiser — Streamlit app.

Run:    streamlit run scripts/wishlist.py

Tabs:
  Build   — compose the wishlist via autocomplete + editable table
  Browse  — filter the matched products catalogue and add directly
  Plans   — run the optimiser, show plans, slide the nursery cap

State lives in two places:
  - st.session_state["wishlist"]  — Wishlist dataclass, survives reruns
  - .wishlist.json (project root) — survives app restarts (atomic write)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import polars as pl
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.common.nurseries import load_nurseries
from src.wishlist.candidates import build_autocomplete_options
from src.wishlist.models import PlantSelector, Wishlist, WishlistRow
from src.wishlist.state import load_wishlist, save_wishlist

PRODUCTS_PARQUET = REPO_ROOT / "data" / "products_matched.parquet"


# --- Data loading (cached) ----------------------------------------------------


@st.cache_data
def _load_products(mtime: float) -> pl.DataFrame:
    """Cached read of products_matched.parquet. Re-runs on mtime change."""
    return pl.read_parquet(PRODUCTS_PARQUET)


@st.cache_data
def _load_nurseries_cached(mtime: float):
    return load_nurseries()


@st.cache_data
def _autocomplete_options(mtime: float):
    df = _load_products(mtime)
    return build_autocomplete_options(df)


# --- Session-state init -------------------------------------------------------


def _init_session_state():
    if "wishlist" not in st.session_state:
        st.session_state["wishlist"] = load_wishlist()
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = "Build"


def _save_wishlist():
    wl: Wishlist = st.session_state["wishlist"]
    wl.updated_at = datetime.now()
    save_wishlist(wl)


# --- Page header --------------------------------------------------------------


def main():
    if not PRODUCTS_PARQUET.exists():
        st.error(
            "`data/products_matched.parquet` is missing. "
            "Run `python load_bronze_data.py --matching` first."
        )
        return

    _init_session_state()
    products_mtime = PRODUCTS_PARQUET.stat().st_mtime

    st.set_page_config(page_title="Blaithin · Wishlist", layout="wide")
    st.title("Blaithin · Wishlist")

    build_tab, browse_tab, plans_tab = st.tabs(["Build", "Browse", "Plans"])

    with build_tab:
        _render_build_tab(products_mtime)

    with browse_tab:
        st.info("Browse tab — implemented in Task 12.")

    with plans_tab:
        st.info("Plans tab — implemented in Task 13.")


# --- Build tab ----------------------------------------------------------------


def _render_build_tab(products_mtime: float):
    options = _autocomplete_options(products_mtime)
    option_by_label = {o.selector.label + f"  ({o.nursery_count} nurseries)": o for o in options}
    sorted_labels = sorted(option_by_label.keys())

    st.subheader("Add to wishlist")
    col_plant, col_qty, col_min, col_br, col_add = st.columns([5, 1, 1, 2, 1])
    with col_plant:
        picked_label = st.selectbox("Plant", options=sorted_labels, key="add_plant")
    with col_qty:
        qty = st.number_input("Qty", min_value=1, value=1, step=1, key="add_qty")
    with col_min:
        min_litres_raw = st.text_input("Min L", value="", key="add_min", placeholder="any")
    with col_br:
        allow_br = st.checkbox("Allow bare-root", value=True, key="add_br")
    with col_add:
        st.write("")
        st.write("")
        add = st.button("+ Add", use_container_width=True)

    if add and picked_label:
        opt = option_by_label[picked_label]
        try:
            min_l = float(min_litres_raw) if min_litres_raw.strip() else None
        except ValueError:
            st.error(f"Min L must be a number (or blank). Got: {min_litres_raw!r}")
            return
        new_row = WishlistRow(
            id=str(uuid4()),
            selector=opt.selector,
            qty=int(qty),
            min_litres=min_l,
            allow_bare_root=bool(allow_br),
            added_at=datetime.now(),
        )
        st.session_state["wishlist"].rows.append(new_row)
        _save_wishlist()
        st.toast(f"Added {opt.selector.label}", icon="✅")

    st.divider()

    wl: Wishlist = st.session_state["wishlist"]
    st.subheader(f"Your wishlist ({len(wl.rows)} row{'s' if len(wl.rows) != 1 else ''})")

    if not wl.rows:
        st.write("Empty — pick a plant above.")
        return

    # Render as an editable data_editor.
    editor_df = pl.DataFrame({
        "id": [r.id for r in wl.rows],
        "Plant": [r.selector.label for r in wl.rows],
        "Qty": [r.qty for r in wl.rows],
        "Min L": [r.min_litres for r in wl.rows],
        "Bare-root?": [r.allow_bare_root for r in wl.rows],
        "Remove": [False] * len(wl.rows),
    }).to_pandas()
    edited = st.data_editor(
        editor_df,
        column_config={
            "id":          st.column_config.TextColumn("id", disabled=True, width="small"),
            "Plant":       st.column_config.TextColumn("Plant", disabled=True, width="large"),
            "Qty":         st.column_config.NumberColumn("Qty", min_value=1, step=1, width="small"),
            "Min L":       st.column_config.NumberColumn("Min L", min_value=0.0, format="%.1f", width="small"),
            "Bare-root?":  st.column_config.CheckboxColumn("Bare-root?", width="small"),
            "Remove":      st.column_config.CheckboxColumn("Remove", width="small"),
        },
        hide_index=True,
        key="wl_editor",
    )

    # Write edits back. Drop rows where Remove is ticked.
    new_rows: list[WishlistRow] = []
    for _, edit_row in edited.iterrows():
        if edit_row["Remove"]:
            continue
        original = next(r for r in wl.rows if r.id == edit_row["id"])
        new_rows.append(WishlistRow(
            id=original.id,
            selector=original.selector,
            qty=int(edit_row["Qty"]),
            min_litres=float(edit_row["Min L"]) if edit_row["Min L"] not in (None, "") else None,
            allow_bare_root=bool(edit_row["Bare-root?"]),
            added_at=original.added_at,
        ))
    if new_rows != wl.rows:
        st.session_state["wishlist"] = Wishlist(rows=new_rows, notes=wl.notes, updated_at=datetime.now())
        _save_wishlist()
        st.rerun()

    st.divider()
    notes = st.text_area("Notes", value=wl.notes, key="wl_notes")
    if notes != wl.notes:
        wl.notes = notes
        _save_wishlist()

    col_clear, col_export, col_find = st.columns([1, 1, 3])
    with col_clear:
        if st.button("Clear all", type="secondary"):
            st.session_state["wishlist"] = Wishlist(rows=[], notes="", updated_at=datetime.now())
            _save_wishlist()
            st.rerun()
    with col_export:
        st.download_button(
            "Export CSV",
            data=_wishlist_to_csv(wl),
            file_name="wishlist.csv",
            mime="text/csv",
        )
    with col_find:
        if st.button("Find best prices →", type="primary"):
            st.session_state["active_tab"] = "Plans"
            st.toast("Switch to the Plans tab to see optimised plans.", icon="📋")


def _wishlist_to_csv(wl: Wishlist) -> str:
    """CSV export of the raw wishlist (not the plan)."""
    import io
    import csv

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["plant_label", "kind", "genus", "species", "cultivar", "category", "qty", "min_litres", "allow_bare_root"])
    for r in wl.rows:
        s = r.selector
        w.writerow([s.label, s.kind, s.genus or "", s.species or "", s.cultivar or "", s.category or "",
                    r.qty, "" if r.min_litres is None else r.min_litres, r.allow_bare_root])
    return buf.getvalue()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Smoke test the Build tab manually**

Run: `streamlit run scripts/wishlist.py`

Expected:
- App opens at `http://localhost:8501`
- Build tab loads with an autocomplete and an empty wishlist table
- Picking a plant + clicking "+ Add" adds a row to the table
- Editing Qty / Min L / Bare-root in the table persists across page interactions
- Ticking "Remove" drops the row on next rerun
- Notes textarea persists
- Refreshing the browser preserves the list (because of .wishlist.json)

Close with Ctrl+C in the terminal when satisfied.

- [ ] **Step 5: Commit**

```bash
git add scripts/wishlist.py requirements.txt
git commit -m "wishlist: Streamlit Build tab (autocomplete + editor + persistence)"
```

---

## Task 12: Streamlit Browse tab

**Files:**
- Modify: `scripts/wishlist.py`

- [ ] **Step 1: Replace the Browse-tab placeholder**

Find this block in `scripts/wishlist.py`:

```python
    with browse_tab:
        st.info("Browse tab — implemented in Task 12.")
```

Replace with:

```python
    with browse_tab:
        _render_browse_tab(products_mtime)
```

Add the implementation function at the bottom of `scripts/wishlist.py`, just above `if __name__ == "__main__":`:

```python
# --- Browse tab ---------------------------------------------------------------


def _render_browse_tab(products_mtime: float):
    df = _load_products(products_mtime)
    nurseries = _load_nurseries_cached((REPO_ROOT / "config" / "nurseries.yaml").stat().st_mtime)
    plants = df.filter(pl.col("is_plant"))

    with st.sidebar:
        st.subheader("Filters")
        genus_choice = st.text_input("Genus contains", value="")
        species_choice = st.text_input("Species contains", value="")
        source_choice = st.multiselect("Source", sorted(plants["source"].unique().to_list()))
        in_stock_only = st.checkbox("In stock only", value=False)
        max_price = st.number_input("Max € (native)", min_value=0.0, value=0.0, step=1.0)

    filtered = plants
    if genus_choice:
        filtered = filtered.filter(pl.col("genus").str.contains(genus_choice, literal=False))
    if species_choice:
        filtered = filtered.filter(pl.col("species").str.contains(species_choice, literal=False))
    if source_choice:
        filtered = filtered.filter(pl.col("source").is_in(source_choice))
    if in_stock_only:
        filtered = filtered.filter(pl.col("stock").is_not_null() & (pl.col("stock") != ""))
    if max_price > 0:
        filtered = filtered.filter(pl.col("price") <= max_price)

    filtered = filtered.sort("price").head(500)

    st.subheader(f"Results ({len(filtered)} rows — showing first 500)")
    if len(filtered) == 0:
        st.write("No matches.")
        return

    cols = ["source", "genus", "species", "cultivar", "size", "size_kind", "pot_size_litres",
            "price", "currency", "stock", "product_url"]
    display = filtered.select(cols).to_pandas()

    st.dataframe(
        display,
        column_config={"product_url": st.column_config.LinkColumn("Product")},
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("---")
    st.subheader("Add a result to your wishlist")
    st.caption("Pick a row by its product_url to add it.")
    urls = display["product_url"].tolist()
    picked_url = st.selectbox("Product", urls, key="browse_pick")
    if picked_url:
        picked = filtered.filter(pl.col("product_url") == picked_url).head(1)
        if len(picked):
            r = picked.row(0, named=True)
            kind = "cultivar" if r["cultivar"] else ("species" if r["species"] else "genus")
            sel = PlantSelector(
                kind=kind,
                genus=r["genus"],
                species=r["species"],
                cultivar=r["cultivar"],
                category=None,
                label=" ".join(filter(None, [r["genus"], r["species"], f"'{r['cultivar']}'" if r["cultivar"] else None])),
            )
            col_q, col_l, col_b, col_a = st.columns([1, 1, 2, 1])
            with col_q:
                bqty = st.number_input("Qty", min_value=1, value=1, key="browse_qty")
            with col_l:
                bmin = st.text_input("Min L", value="", key="browse_min")
            with col_b:
                bbr = st.checkbox("Allow bare-root", value=True, key="browse_br")
            with col_a:
                st.write("")
                st.write("")
                if st.button("+ Add", key="browse_add", use_container_width=True):
                    try:
                        min_l = float(bmin) if bmin.strip() else None
                    except ValueError:
                        st.error(f"Min L must be a number (or blank). Got: {bmin!r}")
                        return
                    new_row = WishlistRow(
                        id=str(uuid4()),
                        selector=sel,
                        qty=int(bqty),
                        min_litres=min_l,
                        allow_bare_root=bool(bbr),
                        added_at=datetime.now(),
                    )
                    st.session_state["wishlist"].rows.append(new_row)
                    _save_wishlist()
                    st.toast(f"Added {sel.label}", icon="✅")
```

- [ ] **Step 2: Smoke test the Browse tab**

Run: `streamlit run scripts/wishlist.py`

Expected:
- Browse tab shows a filterable dataframe of products
- Sidebar filters (genus contains, species contains, source, in-stock, max price) narrow results live
- Selecting a row's product URL + clicking "+ Add" adds it to the wishlist
- Switching back to Build tab shows the new row

- [ ] **Step 3: Commit**

```bash
git add scripts/wishlist.py
git commit -m "wishlist: Streamlit Browse tab with filters + add-from-result"
```

---

## Task 13: Streamlit Plans tab (slider + trade-off table + basket cards)

**Files:**
- Modify: `scripts/wishlist.py`

- [ ] **Step 1: Replace the Plans-tab placeholder**

Find this block in `scripts/wishlist.py`:

```python
    with plans_tab:
        st.info("Plans tab — implemented in Task 13.")
```

Replace with:

```python
    with plans_tab:
        _render_plans_tab(products_mtime)
```

- [ ] **Step 2: Add the optimiser cache wrapper and Plans-tab function**

Add these functions to `scripts/wishlist.py`, just above `if __name__ == "__main__":`:

```python
# --- Plans tab ----------------------------------------------------------------


@st.cache_data
def _run_optimiser(wishlist_payload: str, products_mtime: float, nurseries_mtime: float, fx_mtime: float):
    """Run the optimiser. Cached on a JSON-serialised wishlist signature."""
    import json
    from datetime import date

    from src.wishlist.optimizer import optimise
    from src.wishlist.state import _wishlist_from_dict  # type: ignore

    wl = _wishlist_from_dict(json.loads(wishlist_payload))
    products = _load_products(products_mtime)
    nurseries = _load_nurseries_cached(nurseries_mtime)
    return optimise(wl, products, nurseries, today=date.today())


def _render_plans_tab(products_mtime: float):
    import json

    from src.wishlist.state import _wishlist_to_dict  # type: ignore

    wl: Wishlist = st.session_state["wishlist"]
    if not wl.rows:
        st.info("Add rows to your wishlist on the Build tab, then click 'Find best prices'.")
        return

    nurseries_mtime = (REPO_ROOT / "config" / "nurseries.yaml").stat().st_mtime
    fx_mtime = (REPO_ROOT / "data" / "fx.parquet").stat().st_mtime if (REPO_ROOT / "data" / "fx.parquet").exists() else 0.0
    wishlist_payload = json.dumps(_wishlist_to_dict(wl))

    plans = _run_optimiser(wishlist_payload, products_mtime, nurseries_mtime, fx_mtime)
    if not plans:
        st.warning("No feasible plans — none of your wishlist rows could be fulfilled by any nursery.")
        return

    max_possible = max(len(p.baskets) for p in plans)
    cap_default = min(3, max_possible)
    cap = st.slider("Max nurseries", min_value=1, max_value=min(8, max_possible), value=cap_default)

    # Cheapest plan with len(baskets) <= cap
    eligible = [p for p in plans if len(p.baskets) <= cap]
    if not eligible:
        st.warning(f"No plan with ≤ {cap} nurseries — try a higher cap.")
        return
    chosen = min(eligible, key=lambda p: p.total_eur)

    nurseries = _load_nurseries_cached(nurseries_mtime)
    _render_chosen_plan(chosen, nurseries, wl)

    st.divider()
    _render_tradeoff_table(plans, cap)

    st.divider()
    _render_unfulfilled(chosen, wl, plans)

    st.divider()
    _render_plan_actions(chosen)


def _render_chosen_plan(plan, nurseries, wl):
    st.subheader(f"Cheapest plan using ≤ {len(plan.baskets)} {'nursery' if len(plan.baskets) == 1 else 'nurseries'}")
    for nursery_id, lines in plan.baskets.items():
        cfg = nurseries.get(nursery_id)
        days_old = _days_since_input(lines[0]) if lines else None
        with st.container(border=True):
            header_cols = st.columns([3, 1, 1])
            with header_cols[0]:
                st.markdown(f"**{cfg.display_name if cfg else nursery_id}**  ·  {cfg.base_url if cfg else ''}")
            with header_cols[1]:
                st.caption(f"Currency: {cfg.currency if cfg else '?'}")
            with header_cols[2]:
                st.caption(f"VAT {'incl.' if cfg and cfg.vat_included else 'added'}")
            if days_old is not None:
                st.caption(f"📅 scraped {days_old} days ago")

            line_df = pl.DataFrame([{
                "Plant": l.product_name,
                "Size":  l.size,
                "Qty":   l.qty,
                "Unit €": round(l.unit_price_eur, 2),
                "Line €": round(l.line_eur, 2),
                "URL":   l.product_url,
            } for l in lines]).to_pandas()
            st.dataframe(line_df, column_config={"URL": st.column_config.LinkColumn("Open")}, hide_index=True, use_container_width=True)
            st.markdown(
                f"Subtotal: **€{plan.subtotals_eur[nursery_id]:.2f}**   ·   "
                f"Shipping ({cfg.delivery_type if cfg else '?'}): **€{plan.shipping_eur[nursery_id]:.2f}**   ·   "
                f"Basket total: **€{plan.subtotals_eur[nursery_id] + plan.shipping_eur[nursery_id]:.2f}**"
            )

    fulfilled = sum(len(b) for b in plan.baskets.values())
    requested = len(wl.rows)
    st.markdown(
        f"### Plan total to door: **€{plan.total_eur:.2f}**   ·   "
        f"{fulfilled} / {requested} rows fulfilled"
    )


def _render_tradeoff_table(plans, current_cap: int):
    st.subheader("Trade-off curve")
    max_cap = min(8, max(len(p.baskets) for p in plans))
    rows = []
    best_at_max = min(plans, key=lambda p: p.total_eur).total_eur
    for n in range(1, max_cap + 1):
        eligible = [p for p in plans if len(p.baskets) <= n]
        if not eligible:
            rows.append({"Max nurseries": n, "Total (€)": None, "Rows fulfilled": None, "Δ vs cap=max": None, "Current": n == current_cap})
            continue
        best = min(eligible, key=lambda p: p.total_eur)
        rows.append({
            "Max nurseries": n,
            "Total (€)": round(best.total_eur, 2),
            "Rows fulfilled": f"{sum(len(b) for b in best.baskets.values())}",
            "Δ vs cap=max": round(best.total_eur - best_at_max, 2) if best.total_eur > best_at_max else 0.0,
            "Current": n == current_cap,
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _render_unfulfilled(chosen, wl, all_plans):
    if not chosen.unfulfilled_row_ids:
        return
    with st.expander(f"Couldn't fulfil {len(chosen.unfulfilled_row_ids)} row(s)", expanded=True):
        for row_id in chosen.unfulfilled_row_ids:
            row = next(r for r in wl.rows if r.id == row_id)
            st.markdown(f"- **{row.selector.label}** (qty {row.qty})")
            # Smallest cap that fulfils this row, if any.
            for n in range(len(chosen.baskets) + 1, 9):
                eligible = [p for p in all_plans if len(p.baskets) <= n and row_id not in p.unfulfilled_row_ids]
                if eligible:
                    best = min(eligible, key=lambda p: p.total_eur)
                    st.caption(f"→ Would fulfil at cap={n}: total €{best.total_eur:.2f}")
                    break


def _render_plan_actions(plan):
    import io
    import csv

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["nursery", "plant", "size", "qty", "unit_price_native", "currency", "unit_price_eur", "line_eur", "product_url"])
    for nursery_id, lines in plan.baskets.items():
        for l in lines:
            w.writerow([nursery_id, l.product_name, l.size, l.qty, l.unit_price_native, l.currency,
                        round(l.unit_price_eur, 2), round(l.line_eur, 2), l.product_url])

    st.download_button("Export plan as CSV", data=buf.getvalue(), file_name="plan.csv", mime="text/csv")


def _days_since_input(line) -> int | None:
    """Days between today and the snapshot date of the line's product."""
    from datetime import date as _date
    if line is None or getattr(line, "input_date", None) is None:
        return None
    return (_date.today() - line.input_date).days
```

- [ ] **Step 3: Smoke test the Plans tab**

Run: `streamlit run scripts/wishlist.py`

Expected workflow:
1. Build tab: add 3 rows with distinct plants (e.g., an Acer cultivar, a Rosa cultivar, a Lavandula).
2. Switch to Plans tab. The optimiser runs once and shows the cheapest ≤3-nursery plan.
3. Drag the Max-nurseries slider from 1 to 8 — chosen plan updates and trade-off table highlights the current cap.
4. Click "Export plan as CSV" — file downloads with the expected columns.
5. If any row is unfulfillable at the current cap, the "Couldn't fulfil" section appears with a "Would fulfil at cap=N" hint.

- [ ] **Step 4: Commit**

```bash
git add scripts/wishlist.py
git commit -m "wishlist: Streamlit Plans tab (slider, trade-off, basket cards, CSV export)"
```

---

## Task 14: Final smoke pass + polish

**Files:**
- Modify (potentially): `scripts/wishlist.py`

- [ ] **Step 1: Run the full pytest suite**

Run: `pytest tests/wishlist/ tests/transforms/ -v`
Expected: all tests pass.

- [ ] **Step 2: Run linter**

Run: `ruff check src/wishlist/ src/transforms/ scripts/wishlist.py`
Expected: no errors (or fix any that surface).

- [ ] **Step 3: Manual end-to-end smoke**

```bash
streamlit run scripts/wishlist.py
```

Walk through:
1. App opens. Confirm products_matched.parquet missing produces the friendly error (rename it temporarily to test, then restore).
2. Build tab: add 5 rows mixing granularities (cultivar, species, genus). Edit Qty inline. Set one row to min_litres=3. Set one row to disallow bare-root.
3. Persistence: close the terminal (Ctrl+C), restart streamlit. List restores.
4. Browse tab: filter to a single source (e.g. `tullys`). Add one result.
5. Plans tab: slider 1..8 works. Trade-off table responds. Export CSV.
6. Click Clear all on Build tab. Confirm wishlist empties and `.wishlist.json` is rewritten as empty.

- [ ] **Step 4: Commit any polish fixes (if any)**

```bash
git add -A
git status
git diff --stat
git commit -m "wishlist: smoke-pass polish"  # only if changes
```

If no changes needed, skip the commit and confirm: `git status` shows clean.

- [ ] **Step 5: Final git log check**

Run: `git log --oneline main..HEAD` (or `git log --oneline -20` if you don't have a branch base).
Expected: a clean linear history of one commit per task (14 commits total, give or take if polish was needed).
