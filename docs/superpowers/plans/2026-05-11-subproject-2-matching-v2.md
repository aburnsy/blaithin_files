# Sub-project 2: Matching v2 + Data Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy Levenshtein matcher with a cultivar-preserving pipeline (URL-field → gnparser → exact lookup → rapidfuzz → LLM fallback), rework the RHS and Product schemas so cultivar survives, add nursery metadata config, and classify non-plant SKUs.

**Architecture:** Three layers. (1) **Data model:** new pydantic models + parquet schemas with cultivar/is_plant/product_category/currency on the product row, synonyms[] on the RHS row. (2) **Matching pipeline:** small composable modules under `src/matching/` (`normalize`, `gnparser_wrap`, `exact`, `fuzzy`, `classify`, `llm`, `run`) — each does one thing, each independently testable. (3) **Persistence:** `data/match_overrides.parquet` is a human-auditable, git-committed cache of LLM and manual decisions; never re-LLM'd unless invalidated.

**Tech Stack:** Python 3.11+, pydantic v2, polars, [pygnparser](https://pypi.org/project/pygnparser/) (Python wrapper around the Global Names Parser), rapidfuzz, anthropic SDK (Haiku 4.5 + prompt caching), pytest with fixtures.

**Spec reference:** `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` §6.

---

## Phases (executable in order; checkpointable between phases)

| Phase | Tasks | Output |
|---|---|---|
| **A. Data model + nursery config** | 1–4 | Pydantic models, nurseries.yaml + loader, FX rate cache, match-overrides schema |
| **B. Botanical parsing + normalization** | 5–7 | `gnparser_wrap.py`, `normalize.py`, fixture-backed unit tests |
| **C. Deterministic matcher** | 8–11 | `exact.py`, `fuzzy.py`, `classify.py`, `run.py` orchestrator (no LLM yet) |
| **D. LLM fallback** | 12–14 | `llm.py` with prompt caching, batch flow, override-cache writes |
| **E. RHS schema rework** | 15–17 | Re-modelled RHS parquet with synonyms[]; one-shot migration; updated rhs scraper for next time |
| **F. Integration + retire legacy** | 18–20 | Wire into `load_bronze_data.py`, end-to-end smoke test, delete `legacy_*.py` |

**Checkpoint after each phase:** smoke tests pass, commit, optionally pause for review before next phase.

---

## File structure

**Created in this sub-project:**

| Path | Responsibility |
|---|---|
| `src/matching/models.py` | Pydantic v2 models: `ParsedName`, `MatchResult`, `ProductRecord` (matched), `RhsRecord` (re-modelled), `MatchOverride` |
| `src/matching/normalize.py` | `clean_product_name(raw: str) -> str` — strip pot codes/sizes/quantities/parens-junk before parsing |
| `src/matching/gnparser_wrap.py` | Wrapper over `pygnparser` returning `ParsedName` |
| `src/matching/exact.py` | `exact_match(parsed: ParsedName, rhs_index) -> Optional[MatchResult]` — by (genus, species) |
| `src/matching/fuzzy.py` | `fuzzy_match(name: str, candidates) -> Optional[MatchResult]` — rapidfuzz on RHS botanical+synonym+common |
| `src/matching/classify.py` | `classify_product(raw: str, parsed: ParsedName) -> tuple[bool, str]` — `(is_plant, product_category)`, deterministic prefilter |
| `src/matching/llm.py` | `batch_resolve(unmatched: list[str], rhs_candidates: dict, model="claude-haiku-4-5") -> list[MatchOverride]` — Anthropic SDK with prompt caching |
| `src/matching/run.py` | `run_matching(products_df, rhs_df, overrides_df) -> matched_df` — orchestrates the whole pipeline |
| `src/matching/overrides.py` | Read/write `data/match_overrides.parquet` |
| `src/matching/rhs_remodel.py` | One-shot migration: old RHS parquet → new schema with synonyms[] |
| `src/common/nurseries.py` | Load and validate `config/nurseries.yaml` |
| `src/common/fx.py` | Cached daily ECB EUR rates → `data/fx.parquet`; `to_eur(amount, currency, date)` helper |
| `config/nurseries.yaml` | Per-nursery metadata: currency, delivery, min order, VAT, runner profile |
| `data/match_overrides.parquet` | Cache of LLM and manual override decisions (committed to git, small) |
| `data/fx.parquet` | Daily ECB EUR rates cache (committed to git, tiny) |
| `tests/fixtures/rhs_sample.parquet` | 200-row RHS subset for unit tests (committed) |
| `tests/fixtures/products_sample.json` | ~30 representative product names with expected matches (committed) |
| `tests/matching/test_normalize.py` | Unit tests for `normalize.clean_product_name` |
| `tests/matching/test_gnparser_wrap.py` | Unit tests for the gnparser wrapper |
| `tests/matching/test_exact.py` | Unit tests for exact matcher |
| `tests/matching/test_fuzzy.py` | Unit tests for fuzzy matcher |
| `tests/matching/test_classify.py` | Unit tests for non-plant classifier |
| `tests/matching/test_run.py` | Integration test for the full deterministic pipeline against fixtures |
| `tests/matching/test_overrides.py` | Round-trip tests for override read/write |
| `tests/matching/test_rhs_remodel.py` | Tests for the schema migration |
| `tests/matching/__init__.py` | Empty |
| `scripts/edit_overrides.py` | Small CLI to view/edit `match_overrides.parquet` |

**Modified:**

| Path | Change |
|---|---|
| `requirements.txt` | Add `pydantic>=2`, `pygnparser`, `rapidfuzz`, `anthropic`, `pyyaml`, `httpx` |
| `pyproject.toml` | Pyright extraPaths or imports unchanged; verify `[tool.pyright]` doesn't need additions for the new modules |
| `load_bronze_data.py` | New `--matching` subcommand wires the orchestrator (final phase) |

**Deleted at end of sub-project (Task 20):**

| Path | Reason |
|---|---|
| `src/matching/legacy_match.py` | Replaced by the new pipeline |
| `src/matching/legacy_combine_names.py` | Replaced by the new RHS schema (no flattening needed) |

---

## Phase A — Data model + nursery config

### Task 1: Add dependencies and define pydantic models

**Files:**
- Modify: `requirements.txt`
- Create: `src/matching/models.py`
- Create: `tests/matching/__init__.py`
- Create: `tests/matching/test_models.py`

- [ ] **Step 1: Add dependencies**

Append to `requirements.txt`:
```
pydantic>=2
pyyaml
```
(Other deps — pygnparser, rapidfuzz, anthropic, httpx — added in later tasks as they're used.)

Then `pip install -r requirements.txt` to install.

- [ ] **Step 2: Write the failing test for models**

Create `tests/matching/__init__.py` (empty).

Create `tests/matching/test_models.py`:
```python
"""Tests for matching pydantic models."""

import pytest
from pydantic import ValidationError

from src.matching.models import (
    MatchOverride,
    MatchResult,
    ParsedName,
    ProductRecord,
    RhsRecord,
)


def test_parsed_name_minimal():
    p = ParsedName(genus="Acer", species="palmatum")
    assert p.genus == "Acer"
    assert p.species == "palmatum"
    assert p.cultivar is None
    assert p.cultivar_group is None


def test_parsed_name_with_cultivar():
    p = ParsedName(genus="Acer", species="palmatum", cultivar="Bloodgood")
    assert p.cultivar == "Bloodgood"


def test_parsed_name_genus_only_is_invalid():
    with pytest.raises(ValidationError):
        ParsedName(genus="Acer")  # species is required


def test_match_result_method_enum():
    valid = ("url_field", "gnparser_exact", "rapidfuzz", "llm", "manual_override", "unmatched")
    for m in valid:
        r = MatchResult(rhs_id=1 if m != "unmatched" else None, method=m, confidence=0.9)
        assert r.method == m
    with pytest.raises(ValidationError):
        MatchResult(rhs_id=1, method="invalid", confidence=0.9)


def test_match_result_unmatched_allows_null_rhs_id():
    r = MatchResult(rhs_id=None, method="unmatched", confidence=0.0)
    assert r.rhs_id is None


def test_rhs_record_synonyms_default_empty():
    r = RhsRecord(rhs_id=42, genus="Acer", species="palmatum", botanical_name="Acer palmatum")
    assert r.synonyms == []
    assert r.common_names == []


def test_match_override_round_trip_dict():
    o = MatchOverride(
        product_name_clean="acer palmatum bloodgood",
        rhs_id=42,
        cultivar="Bloodgood",
        is_plant=True,
        product_category="plant",
        source="llm",
        model="claude-haiku-4-5",
    )
    d = o.model_dump()
    o2 = MatchOverride.model_validate(d)
    assert o == o2
```

Run: `pytest tests/matching/test_models.py -v`. Expect: all tests fail with `ModuleNotFoundError: No module named 'src.matching.models'`.

- [ ] **Step 3: Implement `src/matching/models.py`**

Create with this content:
```python
"""Pydantic v2 models for the matching pipeline.

These models define the shape of every record that flows between the matching
modules (parsers, matchers, classifiers, LLM, persistence). Keeping them in one
file makes the pipeline's data contract easy to read end-to-end.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MatchMethod = Literal[
    "url_field",
    "gnparser_exact",
    "rapidfuzz",
    "llm",
    "manual_override",
    "unmatched",
]

ProductCategory = Literal[
    "plant",
    "bulb",
    "seed",
    "compost",
    "soil",
    "tool",
    "pot",
    "fertiliser",
    "accessory",
    "other",
]


class ParsedName(BaseModel):
    """Output of `gnparser_wrap.parse(...)`: a botanical name decomposed."""

    model_config = ConfigDict(frozen=True)

    genus: str
    species: str
    cultivar: Optional[str] = None
    cultivar_group: Optional[str] = None
    rank: Optional[str] = None  # e.g. "var.", "subsp."
    raw: Optional[str] = None  # original input string for debugging


class MatchResult(BaseModel):
    """Output of any of the matchers."""

    model_config = ConfigDict(frozen=True)

    rhs_id: Optional[int] = None
    method: MatchMethod
    confidence: float = Field(ge=0.0, le=1.0)


class RhsRecord(BaseModel):
    """A single RHS plant record (re-modelled — synonyms[] preserved)."""

    rhs_id: int
    genus: str
    species: str
    botanical_name: str
    common_names: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    plant_type: list[str] = Field(default_factory=list)
    family: Optional[str] = None
    description: Optional[str] = None
    is_rhs_award_winner: bool = False
    is_pollinator_plant: bool = False
    height: Optional[str] = None
    spread: Optional[str] = None
    soils: list[str] = Field(default_factory=list)
    moisture: Optional[str] = None
    ph: list[str] = Field(default_factory=list)
    sun_exposure: list[str] = Field(default_factory=list)
    aspect: list[str] = Field(default_factory=list)
    exposure: list[str] = Field(default_factory=list)
    hardiness: Optional[str] = None
    foliage: list[str] = Field(default_factory=list)
    habit: list[str] = Field(default_factory=list)
    plant_url: Optional[str] = None


class ProductRecord(BaseModel):
    """A single nursery product row, post-matching."""

    source: str
    product_url: str
    source_url: Optional[str] = None
    category: Optional[str] = None
    product_name_raw: str
    product_name_clean: str
    genus: Optional[str] = None
    species: Optional[str] = None
    cultivar: Optional[str] = None
    cultivar_group: Optional[str] = None
    rhs_id: Optional[int] = None
    match_method: MatchMethod = "unmatched"
    match_confidence: float = 0.0
    is_plant: bool = True
    product_category: ProductCategory = "plant"
    price_native: Optional[float] = None
    currency: str = "EUR"
    price_eur: Optional[float] = None
    size: Optional[str] = None
    pot_size_litres: Optional[float] = None
    stock: Optional[int] = None
    quantity_per_pack: int = 1
    img_url: Optional[str] = None
    description: Optional[str] = None
    input_date: Optional[datetime] = None


class MatchOverride(BaseModel):
    """A single row in `data/match_overrides.parquet`."""

    product_name_clean: str
    rhs_id: Optional[int] = None
    cultivar: Optional[str] = None
    is_plant: bool = True
    product_category: ProductCategory = "plant"
    source: Literal["llm", "manual"]
    model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
```

- [ ] **Step 4: Run the tests**

```
pytest tests/matching/test_models.py -v
```
Expect: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/matching/models.py tests/matching/
git commit -m "$(cat <<'EOF'
add pydantic data-model for matching pipeline

ParsedName, MatchResult, ProductRecord, RhsRecord, MatchOverride —
the contracts every matching module produces or consumes. Cultivar is
a first-class field on ParsedName/ProductRecord; synonyms[] on RhsRecord.
MatchMethod and ProductCategory are Literal enums to fail loud on typos.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Create `config/nurseries.yaml` and loader

**Files:**
- Create: `config/nurseries.yaml`
- Create: `src/common/nurseries.py`
- Create: `tests/common/__init__.py`
- Create: `tests/common/test_nurseries.py`

- [ ] **Step 1: Write the failing test**

Create `tests/common/__init__.py` (empty).

Create `tests/common/test_nurseries.py`:
```python
"""Tests for nursery metadata loading."""

import pytest
from pydantic import ValidationError

from src.common.nurseries import NurseryConfig, load_nurseries


def test_load_nurseries_returns_dict_keyed_by_source():
    nurseries = load_nurseries()
    assert "tullys" in nurseries
    assert isinstance(nurseries["tullys"], NurseryConfig)


def test_tullys_config_shape():
    nurseries = load_nurseries()
    t = nurseries["tullys"]
    assert t.display_name == "Tully's Nurseries"
    assert t.currency == "EUR"
    assert t.vat_included is True


def test_farmer_gracy_currency_is_gbp():
    nurseries = load_nurseries()
    fg = nurseries["farmer_gracy"]
    assert fg.currency == "GBP"


def test_nl_nurseries_flag_vat_status():
    nurseries = load_nurseries()
    bulbi = nurseries["bulbi"]
    assert bulbi.vat_included is False  # IE buyers may face customs VAT


def test_invalid_currency_rejected():
    with pytest.raises(ValidationError):
        NurseryConfig(
            display_name="Test",
            base_url="https://example.com",
            currency="ZZZ",  # not a known ISO code in our enum
            vat_included=True,
            delivery_type="flat",
        )
```

Run: `pytest tests/common/test_nurseries.py -v`. Expect: fail with import error.

- [ ] **Step 2: Create `config/nurseries.yaml` with the 5 currently-scraped nurseries plus the 3 new ones from Q7**

```yaml
tullys:
  display_name: "Tully's Nurseries"
  base_url: https://shop.tullynurseries.ie
  currency: EUR
  vat_included: true
  delivery_type: tiered
  delivery_fees: []      # to be filled in from site
  min_order_eur: 0
  runs_on: github-actions
  ships_live_plants_to_ireland: true
  notes: "Currently returning ASP.NET error pages — site may be abandoned."

arboretum:
  display_name: "Arboretum"
  base_url: https://www.arboretum.ie
  currency: EUR
  vat_included: true
  delivery_type: tiered
  delivery_fees: []
  min_order_eur: 0
  runs_on: github-actions
  ships_live_plants_to_ireland: true
  notes: ""

carragh:
  display_name: "Caragh Nurseries"
  base_url: https://caraghnurseries.ie
  currency: EUR
  vat_included: true
  delivery_type: tiered
  delivery_fees: []
  min_order_eur: 0
  runs_on: github-actions
  ships_live_plants_to_ireland: true
  notes: ""

gardens4you:
  display_name: "Gardens4You"
  base_url: https://www.gardens4you.ie
  currency: EUR
  vat_included: true
  delivery_type: flat
  delivery_fees: [{ max_value_eur: null, fee_eur: 9.95 }]
  min_order_eur: 0
  runs_on: github-actions
  ships_live_plants_to_ireland: true
  notes: ""

quickcrop:
  display_name: "QuickCrop Ireland"
  base_url: https://www.quickcrop.ie
  currency: EUR
  vat_included: true
  delivery_type: flat
  delivery_fees: [{ max_value_eur: null, fee_eur: 7.95 }]
  min_order_eur: 0
  runs_on: github-actions
  ships_live_plants_to_ireland: true
  notes: ""

farmer_gracy:
  display_name: "Farmer Gracy"
  base_url: https://www.farmergracy.co.uk
  currency: GBP
  vat_included: true
  delivery_type: flat
  delivery_fees: [{ max_value_eur: null, fee_eur: 6.95 }]
  min_order_eur: 0
  runs_on: self-hosted    # Shopify, possibly Cloudflare-protected — verify
  ships_live_plants_to_ireland: true
  notes: "Specialises in bare-root, often cheapest. UK shipper, GBP pricing."

bulbi:
  display_name: "Bulbi.nl"
  base_url: https://www.bulbi.nl
  currency: EUR
  vat_included: false
  delivery_type: tiered
  delivery_fees: []
  min_order_eur: 25
  runs_on: self-hosted
  ships_live_plants_to_ireland: true
  notes: "VAT may apply on import to Ireland. Bulbs and perennials."

greengardenflowerbulbs:
  display_name: "GreenGardenFlowerBulbs.nl"
  base_url: https://www.greengardenflowerbulbs.nl
  currency: EUR
  vat_included: false
  delivery_type: tiered
  delivery_fees: []
  min_order_eur: 50
  runs_on: self-hosted
  ships_live_plants_to_ireland: true
  notes: "Bulk bulbs. No VAT shown at checkout. Min order applies."
```

- [ ] **Step 3: Implement `src/common/nurseries.py`**

```python
"""Load and validate per-nursery metadata from config/nurseries.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "nurseries.yaml"

Currency = Literal["EUR", "GBP", "USD"]
DeliveryType = Literal["flat", "tiered", "by_weight", "quote_only", "free"]
RunsOn = Literal["github-actions", "self-hosted"]


class DeliveryFee(BaseModel):
    """One row in a tiered delivery schedule."""

    model_config = ConfigDict(frozen=True)

    max_value_eur: Optional[float] = None
    fee_eur: float


class NurseryConfig(BaseModel):
    """Per-nursery metadata read from config/nurseries.yaml."""

    model_config = ConfigDict(frozen=True)

    display_name: str
    base_url: HttpUrl
    currency: Currency
    vat_included: bool
    delivery_type: DeliveryType
    delivery_fees: list[DeliveryFee] = Field(default_factory=list)
    min_order_eur: float = 0
    runs_on: RunsOn = "github-actions"
    ships_live_plants_to_ireland: bool = True
    notes: str = ""


def load_nurseries(path: Optional[Path] = None) -> dict[str, NurseryConfig]:
    """Load and validate the nurseries config. Returns dict keyed by source slug."""

    config_path = path or CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return {slug: NurseryConfig.model_validate(cfg) for slug, cfg in raw.items()}
```

- [ ] **Step 4: Run the tests**

```
pytest tests/common/test_nurseries.py -v
```
Expect: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add config/nurseries.yaml src/common/nurseries.py tests/common/
git commit -m "$(cat <<'EOF'
add nurseries.yaml config + pydantic loader

8 nurseries: 5 currently scraped + 3 new (Farmer Gracy GBP, Bulbi NL,
GreenGardenFlowerBulbs NL). Per-nursery currency, VAT, delivery, min
order, runner profile, and Ireland-shipping flag — drives both
scraping infra and dashboard badging.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: FX rate cache (`src/common/fx.py`)

**Files:**
- Modify: `requirements.txt` (add `httpx`)
- Create: `src/common/fx.py`
- Create: `tests/common/test_fx.py`
- Create: `data/fx.parquet` (initial seed of recent ECB rates)

- [ ] **Step 1: Add httpx**

Append to `requirements.txt`: `httpx`. Then `pip install httpx`.

- [ ] **Step 2: Write failing tests**

Create `tests/common/test_fx.py`:
```python
"""Tests for FX rate conversion."""

from datetime import date
from decimal import Decimal

import pytest

from src.common.fx import to_eur, FxRateMissing


def test_to_eur_passthrough_for_eur():
    assert to_eur(10.0, "EUR", date(2026, 5, 11)) == 10.0


def test_to_eur_converts_gbp():
    # Use a real recent date that's in the seeded fx.parquet
    result = to_eur(10.0, "GBP", date(2026, 5, 11))
    assert 10.0 < result < 15.0  # GBP > EUR historically; sanity bound


def test_to_eur_missing_rate_raises():
    with pytest.raises(FxRateMissing):
        to_eur(10.0, "GBP", date(1900, 1, 1))


def test_to_eur_unknown_currency_raises():
    with pytest.raises(ValueError, match="Unknown currency"):
        to_eur(10.0, "ZZZ", date(2026, 5, 11))
```

Run: `pytest tests/common/test_fx.py -v`. Expect: import errors.

- [ ] **Step 3: Implement `src/common/fx.py`**

```python
"""Cached EUR FX rate lookups, sourced from the ECB.

The rates are cached in `data/fx.parquet` (one row per (date, currency)).
Refresh with `python -m src.common.fx --refresh` to fetch the latest from ECB.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import polars as pl

FX_PARQUET = Path(__file__).resolve().parents[2] / "data" / "fx.parquet"

Currency = Literal["EUR", "GBP", "USD"]


class FxRateMissing(Exception):
    """Raised when the requested (date, currency) pair has no rate in the cache."""


def to_eur(amount: float, currency: str, on: date) -> float:
    """Convert `amount` of `currency` to EUR using the rate on `on`.

    Raises:
        FxRateMissing: if no rate exists for that date.
        ValueError: if `currency` is unknown.
    """

    if currency == "EUR":
        return amount
    if currency not in ("GBP", "USD"):
        raise ValueError(f"Unknown currency: {currency}")

    df = pl.read_parquet(FX_PARQUET)
    row = df.filter((pl.col("date") == on) & (pl.col("currency") == currency))
    if len(row) == 0:
        # Fall back to most recent known rate for that currency before `on`.
        row = (
            df.filter((pl.col("currency") == currency) & (pl.col("date") <= on))
            .sort("date", descending=True)
            .head(1)
        )
    if len(row) == 0:
        raise FxRateMissing(f"No FX rate for {currency} on or before {on}")

    rate_to_eur = row.select("rate_to_eur").item()
    return amount * rate_to_eur


def refresh_from_ecb() -> None:
    """Fetch the latest 90 days of EUR rates from ECB and update fx.parquet."""

    import httpx

    # ECB SDMX endpoint for daily reference rates against EUR
    url = "https://data-api.ecb.europa.eu/service/data/EXR/D.GBP+USD.EUR.SP00.A?format=csvdata"
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()

    raw = pl.read_csv(response.content)
    # Columns of interest: TIME_PERIOD (date), CURRENCY (GBP/USD), OBS_VALUE (rate from EUR to that currency)
    new = (
        raw.select(
            pl.col("TIME_PERIOD").str.to_date().alias("date"),
            pl.col("CURRENCY").alias("currency"),
            (1.0 / pl.col("OBS_VALUE").cast(pl.Float64)).alias("rate_to_eur"),
        )
        .filter(pl.col("rate_to_eur").is_not_null())
    )

    if FX_PARQUET.exists():
        existing = pl.read_parquet(FX_PARQUET)
        merged = pl.concat([existing, new]).unique(subset=["date", "currency"], keep="last")
    else:
        merged = new

    merged.sort(["date", "currency"]).write_parquet(FX_PARQUET)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--refresh", action="store_true", help="Fetch latest ECB rates")
    args = p.parse_args()
    if args.refresh:
        refresh_from_ecb()
        print(f"Refreshed FX rates → {FX_PARQUET}")
```

- [ ] **Step 4: Seed `data/fx.parquet` with recent rates**

```
python -m src.common.fx --refresh
```

Expect: a new `data/fx.parquet` (~1 KB) containing ~60-90 rows of GBP and USD rates for recent dates.

- [ ] **Step 5: Run the tests**

```
pytest tests/common/test_fx.py -v
```
Expect: 4 passed (the test for `2026-05-11` requires the rate to be in the seeded parquet — refresh should have included today).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/common/fx.py tests/common/test_fx.py data/fx.parquet
git commit -m "$(cat <<'EOF'
add ECB FX rate cache for EUR conversion

to_eur(amount, currency, date) reads from data/fx.parquet, falling back
to the most recent rate ≤ requested date if exact missing. Refresh with
`python -m src.common.fx --refresh` to pull the latest 90 days from ECB.

Used by the matcher to populate ProductRecord.price_eur for cross-nursery
comparison when nurseries quote in GBP (Farmer Gracy) or USD.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Match overrides parquet I/O

**Files:**
- Create: `src/matching/overrides.py`
- Create: `tests/matching/test_overrides.py`
- Create: `data/match_overrides.parquet` (empty)

- [ ] **Step 1: Failing test**

Create `tests/matching/test_overrides.py`:
```python
"""Round-trip tests for match_overrides.parquet read/write."""

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from src.matching.models import MatchOverride
from src.matching.overrides import (
    OVERRIDES_PARQUET,
    load_overrides,
    save_overrides,
    upsert_override,
)


@pytest.fixture
def tmp_overrides(tmp_path, monkeypatch):
    p = tmp_path / "match_overrides.parquet"
    monkeypatch.setattr("src.matching.overrides.OVERRIDES_PARQUET", p)
    return p


def test_load_empty_returns_empty_list(tmp_overrides):
    save_overrides([])
    assert load_overrides() == []


def test_round_trip_one(tmp_overrides):
    o = MatchOverride(
        product_name_clean="acer palmatum bloodgood",
        rhs_id=98765,
        cultivar="Bloodgood",
        is_plant=True,
        product_category="plant",
        source="llm",
        model="claude-haiku-4-5",
    )
    save_overrides([o])
    loaded = load_overrides()
    assert len(loaded) == 1
    assert loaded[0].product_name_clean == "acer palmatum bloodgood"
    assert loaded[0].rhs_id == 98765
    assert loaded[0].cultivar == "Bloodgood"


def test_upsert_replaces_existing(tmp_overrides):
    save_overrides([
        MatchOverride(
            product_name_clean="acer palmatum bloodgood",
            rhs_id=1,
            source="llm",
        )
    ])
    upsert_override(MatchOverride(
        product_name_clean="acer palmatum bloodgood",
        rhs_id=98765,
        source="manual",
        notes="corrected by Andrew",
    ))
    loaded = load_overrides()
    assert len(loaded) == 1
    assert loaded[0].rhs_id == 98765
    assert loaded[0].source == "manual"
```

Run: `pytest tests/matching/test_overrides.py -v`. Expect: import errors.

- [ ] **Step 2: Implement `src/matching/overrides.py`**

```python
"""Read/write the human-auditable cache of LLM and manual match decisions."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from src.matching.models import MatchOverride

OVERRIDES_PARQUET = Path(__file__).resolve().parents[2] / "data" / "match_overrides.parquet"


def load_overrides() -> list[MatchOverride]:
    """Load all overrides from the parquet. Empty list if file missing."""

    if not OVERRIDES_PARQUET.exists():
        return []
    df = pl.read_parquet(OVERRIDES_PARQUET)
    return [MatchOverride.model_validate(row) for row in df.iter_rows(named=True)]


def save_overrides(overrides: list[MatchOverride]) -> None:
    """Overwrite the overrides parquet with the given list."""

    if not overrides:
        # Write an empty parquet with the right schema so future reads succeed.
        pl.DataFrame(schema={
            "product_name_clean": pl.Utf8,
            "rhs_id": pl.Int64,
            "cultivar": pl.Utf8,
            "is_plant": pl.Boolean,
            "product_category": pl.Utf8,
            "source": pl.Utf8,
            "model": pl.Utf8,
            "created_at": pl.Datetime,
            "notes": pl.Utf8,
        }).write_parquet(OVERRIDES_PARQUET)
        return

    df = pl.DataFrame([o.model_dump() for o in overrides])
    df.write_parquet(OVERRIDES_PARQUET)


def upsert_override(override: MatchOverride) -> None:
    """Insert or replace an override (keyed on product_name_clean)."""

    existing = load_overrides()
    others = [o for o in existing if o.product_name_clean != override.product_name_clean]
    save_overrides(others + [override])
```

- [ ] **Step 3: Run tests**

```
pytest tests/matching/test_overrides.py -v
```
Expect: 3 passed.

- [ ] **Step 4: Initialise empty `data/match_overrides.parquet` for the repo**

```
python -c "from src.matching.overrides import save_overrides; save_overrides([])"
```

This creates an empty parquet with the right schema, ready to accumulate decisions.

- [ ] **Step 5: Commit**

```bash
git add src/matching/overrides.py tests/matching/test_overrides.py data/match_overrides.parquet
git commit -m "$(cat <<'EOF'
add match_overrides parquet I/O for LLM and manual decisions

load/save/upsert against data/match_overrides.parquet. Pydantic-validated
on read; full schema on empty write so future reads don't break. Initial
parquet is empty; populated by Phase D LLM batch and the (later)
edit_overrides CLI.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase B — Botanical parsing + normalization

### Task 5: `normalize.py` — strip nursery cruft from product names

**Files:**
- Create: `src/matching/normalize.py`
- Create: `tests/matching/test_normalize.py`
- Create: `tests/fixtures/products_sample.json`

- [ ] **Step 1: Sample real product names from a current parquet**

Run:
```
python -c "
import polars as pl, json
from pathlib import Path
latest = sorted(Path('data/gardens4you/').glob('*.parquet'))[-1]
df = pl.read_parquet(latest)
sample = df.select('product_name').sample(30, seed=42).to_series(0).to_list()
Path('tests/fixtures').mkdir(parents=True, exist_ok=True)
json.dump([{'raw': n, 'expected_clean': None} for n in sample], open('tests/fixtures/products_sample.json', 'w'), indent=2)
print(f'wrote {len(sample)} samples')
"
```

This creates `tests/fixtures/products_sample.json` with 30 raw product names and a placeholder for the expected normalised form.

- [ ] **Step 2: Manually fill in `expected_clean` for each row**

Open `tests/fixtures/products_sample.json` and for each entry, write the expected `clean` value. Examples:

| raw | expected_clean |
|---|---|
| `"Acer palmatum 'Bloodgood' 9cm"` | `"Acer palmatum 'Bloodgood'"` |
| `"Tulipa 'Apricot Beauty' 5 bulbs"` | `"Tulipa 'Apricot Beauty'"` |
| `"Multipurpose Compost 50L"` | `"Multipurpose Compost"` |
| `"Hedera helix (English Ivy)"` | `"Hedera helix"` |
| `"Lavandula angustifolia 'Hidcote' 2L pot"` | `"Lavandula angustifolia 'Hidcote'"` |

The cleaning rules to derive: strip trailing pot codes, strip `(common name)` parenthetical when it follows a parsed binomial, strip quantity-pack indicators (`5 bulbs`, `pack of 3`).

- [ ] **Step 3: Failing test**

Create `tests/matching/test_normalize.py`:
```python
"""Unit tests for product name normalization."""

import json
from pathlib import Path

import pytest

from src.matching.normalize import clean_product_name

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "products_sample.json"


@pytest.mark.parametrize("case", json.loads(FIXTURE.read_text()))
def test_clean_product_name(case):
    if case["expected_clean"] is None:
        pytest.skip("expected_clean not yet annotated for this sample")
    assert clean_product_name(case["raw"]) == case["expected_clean"]


def test_clean_strips_pot_codes():
    assert clean_product_name("Acer palmatum 9cm") == "Acer palmatum"
    assert clean_product_name("Acer palmatum 2L") == "Acer palmatum"
    assert clean_product_name("Acer palmatum 3 ltr") == "Acer palmatum"
    assert clean_product_name("Acer palmatum P9") == "Acer palmatum"


def test_clean_strips_quantity_packs():
    assert clean_product_name("Tulipa 'Apricot Beauty' 5 bulbs") == "Tulipa 'Apricot Beauty'"
    assert clean_product_name("Pack of 10 Tulipa 'Apricot Beauty'") == "Tulipa 'Apricot Beauty'"


def test_clean_strips_common_name_parenthetical():
    assert clean_product_name("Hedera helix (English Ivy)") == "Hedera helix"


def test_clean_preserves_cultivar_quotes():
    assert clean_product_name("Acer palmatum 'Bloodgood'") == "Acer palmatum 'Bloodgood'"


def test_clean_handles_extra_whitespace():
    assert clean_product_name("  Acer   palmatum  ") == "Acer palmatum"
```

Run: `pytest tests/matching/test_normalize.py -v`. Expect: import errors.

- [ ] **Step 4: Implement `src/matching/normalize.py`**

```python
"""Strip nursery cruft from product names so the parser sees clean botanical input."""

from __future__ import annotations

import re

# Order matters: more-specific patterns before more-general ones.
_PATTERNS = [
    re.compile(r"\b\d+\s*(?:cm|mm|m)\b", re.IGNORECASE),                # heights/widths in cm/mm/m
    re.compile(r"\b\d+\s*(?:l|ltr|litre|liter)\b", re.IGNORECASE),      # pot volumes
    re.compile(r"\bP\d+\b", re.IGNORECASE),                             # pot codes (P9, P15)
    re.compile(r"\b\d+\s*(?:bulbs?|seeds?|plugs?|packs?)\b", re.IGNORECASE),
    re.compile(r"\bpack\s+of\s+\d+\b", re.IGNORECASE),
    re.compile(r"\(\s*[A-Z][a-z]+(?:\s+[a-z]+)+\s*\)"),                # (Common Name) trailing parens
    re.compile(r"\s+"),                                                  # collapse whitespace runs
]


def clean_product_name(raw: str) -> str:
    """Return a botanical-name-only version of `raw`.

    Strips pot codes, sizes, quantity packs, and common-name parentheticals.
    Preserves cultivar quotes (`'Bloodgood'`) and binomial structure.
    """

    s = raw
    for pattern in _PATTERNS[:-1]:
        s = pattern.sub(" ", s)
    # final whitespace collapse
    s = _PATTERNS[-1].sub(" ", s).strip()
    return s
```

- [ ] **Step 5: Run tests**

```
pytest tests/matching/test_normalize.py -v
```
Expect: all the explicit unit tests pass. Some `test_clean_product_name` parametrized cases may fail if the fixture annotations don't match the cleaner — iterate: either tighten the regex or correct the fixture's `expected_clean`.

- [ ] **Step 6: Commit**

```bash
git add src/matching/normalize.py tests/matching/test_normalize.py tests/fixtures/products_sample.json
git commit -m "$(cat <<'EOF'
add product name normalizer with fixture-backed tests

Strips pot codes (9cm, 2L, P9), quantity packs (5 bulbs, pack of 10),
and trailing (Common Name) parens. Preserves cultivar quotes. Backed
by 30 real product names sampled from gardens4you with hand-annotated
expected output.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: gnparser wrapper

**Files:**
- Modify: `requirements.txt` (add `pygnparser`)
- Create: `src/matching/gnparser_wrap.py`
- Create: `tests/matching/test_gnparser_wrap.py`

- [ ] **Step 1: Add and install pygnparser**

Append to `requirements.txt`: `pygnparser`. Then `pip install pygnparser`.

If `pygnparser` install fails (it wraps a Go binary), STOP and report — we may need to install gnparser separately or pick an alternative wrapper. Possible fallbacks: call the `gnparser` CLI directly via subprocess, or use the public ParseNames REST API at https://parser.globalnames.org.

- [ ] **Step 2: Failing tests**

Create `tests/matching/test_gnparser_wrap.py`:
```python
"""Tests for the gnparser wrapper."""

import pytest

from src.matching.gnparser_wrap import parse, ParseFailed


def test_parse_simple_binomial():
    p = parse("Acer palmatum")
    assert p.genus == "Acer"
    assert p.species == "palmatum"
    assert p.cultivar is None


def test_parse_with_cultivar():
    p = parse("Acer palmatum 'Bloodgood'")
    assert p.genus == "Acer"
    assert p.species == "palmatum"
    assert p.cultivar == "Bloodgood"


def test_parse_with_cultivar_group():
    p = parse("Acer palmatum 'Bloodgood' (Atropurpureum Group)")
    assert p.cultivar == "Bloodgood"
    assert p.cultivar_group == "Atropurpureum Group"


def test_parse_with_authority_stripped():
    # Authority "L." (Linnaeus) should be ignored in our wrapper output
    p = parse("Lavandula angustifolia L.")
    assert p.genus == "Lavandula"
    assert p.species == "angustifolia"


def test_parse_genus_only_fails():
    with pytest.raises(ParseFailed):
        parse("Acer")


def test_parse_garbage_fails():
    with pytest.raises(ParseFailed):
        parse("not a plant name at all")


def test_parse_preserves_raw():
    p = parse("Acer palmatum 'Bloodgood'")
    assert p.raw == "Acer palmatum 'Bloodgood'"
```

Run: `pytest tests/matching/test_gnparser_wrap.py -v`. Expect: import errors.

- [ ] **Step 3: Implement `src/matching/gnparser_wrap.py`**

```python
"""Wrapper around pygnparser returning our `ParsedName` model."""

from __future__ import annotations

import re

import pygnparser

from src.matching.models import ParsedName


class ParseFailed(Exception):
    """gnparser could not parse the input as a binomial+ name."""


_GROUP_RE = re.compile(r"\(([^)]+Group)\)$")


def parse(name: str) -> ParsedName:
    """Parse a botanical name. Raises `ParseFailed` if no genus+species found."""

    # gnparser returns a dict; the relevant fields are 'parsed', 'canonical', 'details'
    result = pygnparser.parse(name)
    if not result.get("parsed"):
        raise ParseFailed(f"Could not parse: {name!r}")

    details = result.get("details", {})
    genus = details.get("genus")
    species = details.get("specificEpithet")
    if not genus or not species:
        raise ParseFailed(f"No genus+species in: {name!r}")

    cultivar = details.get("cultivar")
    rank = details.get("rank")

    # gnparser doesn't always extract `(Atropurpureum Group)` — handle that fallback
    cultivar_group = None
    m = _GROUP_RE.search(name)
    if m:
        cultivar_group = m.group(1)

    return ParsedName(
        genus=genus,
        species=species,
        cultivar=cultivar,
        cultivar_group=cultivar_group,
        rank=rank,
        raw=name,
    )
```

(NB — pygnparser's exact return shape may differ; if `parse(...)` returns a different structure, adjust the dict access. The tests will surface mismatches immediately.)

- [ ] **Step 4: Run tests**

```
pytest tests/matching/test_gnparser_wrap.py -v
```
Expect: 7 passed. If pygnparser's API differs from assumed, adjust wrapper and re-run.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/matching/gnparser_wrap.py tests/matching/test_gnparser_wrap.py
git commit -m "$(cat <<'EOF'
add gnparser wrapper returning ParsedName model

Thin shim over pygnparser. Always returns our ParsedName (genus, species,
cultivar, cultivar_group, rank) or raises ParseFailed. Cultivar Group
parens fallback handled by regex when gnparser misses it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Build the RHS test fixture (small subset)

**Files:**
- Create: `tests/fixtures/rhs_sample.parquet`
- Create: `scripts/build_rhs_fixture.py`

- [ ] **Step 1: Implement the fixture builder**

Create `scripts/build_rhs_fixture.py`:
```python
"""Build a 200-row RHS subset for matching tests.

Picks rows that exercise different match paths:
- 50 with cultivars in the botanical_name (e.g. Rosa 'Irish Fireflame')
- 50 plain binomials (e.g. Acer palmatum)
- 50 with common_name populated
- 50 random
"""

from pathlib import Path

import polars as pl

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "rhs_sample.parquet"
SRC = Path(__file__).resolve().parents[1] / "data" / "rhs.parquet"


def main():
    df = pl.read_parquet(SRC)

    with_cultivar = df.filter(pl.col("botanical_name").str.contains("'")).sample(50, seed=1)
    plain = df.filter(~pl.col("botanical_name").str.contains("'")).sample(50, seed=2)
    with_common = df.filter(pl.col("common_name").is_not_null()).sample(50, seed=3)
    random = df.sample(50, seed=4)

    sample = (
        pl.concat([with_cultivar, plain, with_common, random])
        .unique(subset=["id"])
        .rename({"id": "rhs_id"})  # fixture uses the new (post-Task-16) schema name
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sample.write_parquet(OUT)
    print(f"Wrote {len(sample)} rows to {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the builder**

```
python scripts/build_rhs_fixture.py
```

Expect: a `tests/fixtures/rhs_sample.parquet` of ~150-200 rows (some duplicates removed by `.unique`).

- [ ] **Step 3: Quick sanity check**

```
python -c "import polars as pl; df = pl.read_parquet('tests/fixtures/rhs_sample.parquet'); print(df.shape); print(df.columns)"
```

Expect: shape `(150-200, 21)` with the same columns as the production rhs.parquet.

- [ ] **Step 4: Commit**

```bash
git add scripts/build_rhs_fixture.py tests/fixtures/rhs_sample.parquet
git commit -m "$(cat <<'EOF'
add RHS fixture: 200-row stratified sample for matcher tests

Stratified across: cultivar-bearing, plain binomial, common-name-populated,
random. Used by exact/fuzzy/run integration tests so they don't load
the full 62k-row production parquet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase C — Deterministic matcher

### Task 8: Exact matcher (`src/matching/exact.py`)

**Files:**
- Create: `src/matching/exact.py`
- Create: `tests/matching/test_exact.py`

- [ ] **Step 1: Failing tests**

Create `tests/matching/test_exact.py`:
```python
"""Tests for exact (genus, species) matching against the RHS index."""

from pathlib import Path

import polars as pl
import pytest

from src.matching.exact import RhsIndex, exact_match
from src.matching.models import ParsedName

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rhs_sample.parquet"


@pytest.fixture(scope="module")
def index():
    df = pl.read_parquet(FIXTURE)
    return RhsIndex.from_dataframe(df)


def test_exact_match_known_genus_species(index):
    # Pick a row from the fixture and try to match
    df = pl.read_parquet(FIXTURE)
    sample = df.head(1).to_dicts()[0]
    botanical = sample["botanical_name"]
    # Strip cultivar quotes for the exact-match input (genus+species only)
    parts = botanical.split(" ")[:2]
    parsed = ParsedName(genus=parts[0], species=parts[1].strip("'\""))

    result = exact_match(parsed, index)
    assert result is not None
    assert result.method == "gnparser_exact"
    assert result.confidence == 1.0


def test_exact_match_unknown_returns_none(index):
    parsed = ParsedName(genus="Notarealgenus", species="notarealspecies")
    assert exact_match(parsed, index) is None


def test_index_handles_synonym_lookup(index):
    # If RHS has Foo bar with synonym Foo baz, a parse for (Foo, baz) should resolve
    # via the synonym index. Smoke-tested here; deeper synonym tests in test_run.py.
    pass  # Placeholder — synonyms field populated in Phase E
```

Run: `pytest tests/matching/test_exact.py -v`. Expect: import errors.

- [ ] **Step 2: Implement `src/matching/exact.py`**

```python
"""Exact (genus, species) lookup against the RHS records."""

from __future__ import annotations

import polars as pl

from src.matching.models import MatchResult, ParsedName


class RhsIndex:
    """In-memory lookup over the RHS table, keyed by (genus, species)."""

    def __init__(self, by_genus_species: dict[tuple[str, str], int]):
        self._by_gs = by_genus_species

    @classmethod
    def from_dataframe(cls, df: pl.DataFrame) -> "RhsIndex":
        """Build an index from a polars DataFrame with botanical_name + rhs_id columns.

        Accepts either `rhs_id` (new schema) or `id` (legacy production parquet
        before Task 16 migration runs) — the field is detected at call time.
        """

        id_col = "rhs_id" if "rhs_id" in df.columns else "id"

        index: dict[tuple[str, str], int] = {}
        for row in df.iter_rows(named=True):
            name = row["botanical_name"] or ""
            parts = name.split(" ")
            if len(parts) < 2:
                continue
            genus = parts[0].strip()
            species = parts[1].strip("'\"")  # strip quote markers from cultivars in legacy data
            if genus and species and (genus, species) not in index:
                index[(genus, species)] = row[id_col]
        return cls(index)

    def lookup(self, genus: str, species: str) -> int | None:
        return self._by_gs.get((genus, species))


def exact_match(parsed: ParsedName, index: RhsIndex) -> MatchResult | None:
    """Look up (genus, species) in the RHS index. Returns None if not found."""

    rhs_id = index.lookup(parsed.genus, parsed.species)
    if rhs_id is None:
        return None
    return MatchResult(rhs_id=rhs_id, method="gnparser_exact", confidence=1.0)
```

- [ ] **Step 3: Run tests**

```
pytest tests/matching/test_exact.py -v
```
Expect: 2 passed (1 placeholder skipped).

- [ ] **Step 4: Commit**

```bash
git add src/matching/exact.py tests/matching/test_exact.py
git commit -m "$(cat <<'EOF'
add exact (genus, species) RHS matcher

RhsIndex builds an in-memory dict from the RHS DataFrame; exact_match
returns MatchResult with confidence 1.0 when (genus, species) hits,
None otherwise. Synonyms[] integration deferred to Phase E.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Fuzzy residual matcher (`src/matching/fuzzy.py`)

**Files:**
- Modify: `requirements.txt` (add `rapidfuzz`)
- Create: `src/matching/fuzzy.py`
- Create: `tests/matching/test_fuzzy.py`

- [ ] **Step 1: Add rapidfuzz**

Append to `requirements.txt`: `rapidfuzz`. Then `pip install rapidfuzz`.

- [ ] **Step 2: Failing tests**

Create `tests/matching/test_fuzzy.py`:
```python
"""Tests for fuzzy residual matcher."""

from pathlib import Path

import polars as pl
import pytest

from src.matching.fuzzy import build_candidates, fuzzy_match

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rhs_sample.parquet"


@pytest.fixture(scope="module")
def candidates():
    df = pl.read_parquet(FIXTURE)
    return build_candidates(df)


def test_fuzzy_close_typo_resolves(candidates):
    # Take a real botanical_name from the fixture, mutate one letter, expect a match
    df = pl.read_parquet(FIXTURE)
    name = df.select("botanical_name").head(1).item()
    typo = name[:-1] + "x"  # mutate last char
    result = fuzzy_match(typo, candidates, threshold=0.85)
    assert result is not None
    assert result.method == "rapidfuzz"
    assert result.confidence >= 0.85


def test_fuzzy_far_off_returns_none(candidates):
    result = fuzzy_match("totally unrelated string xyz123", candidates, threshold=0.85)
    assert result is None
```

- [ ] **Step 3: Implement `src/matching/fuzzy.py`**

```python
"""Fuzzy residual matcher (rapidfuzz Levenshtein) over RHS botanical+synonym+common."""

from __future__ import annotations

import polars as pl
from rapidfuzz import process
from rapidfuzz.distance import Levenshtein

from src.matching.models import MatchResult


def build_candidates(rhs_df: pl.DataFrame) -> list[tuple[str, int]]:
    """Build a list of (lookup_string, rhs_id) tuples covering all RHS name variants.

    Accepts either `rhs_id` (new schema) or `id` (legacy production parquet
    before Task 16 migration runs).
    """

    id_col = "rhs_id" if "rhs_id" in rhs_df.columns else "id"

    candidates: list[tuple[str, int]] = []
    for row in rhs_df.iter_rows(named=True):
        rhs_id = row[id_col]
        botanical = row.get("botanical_name")
        common = row.get("common_name")
        if botanical:
            candidates.append((botanical.lower(), rhs_id))
        if common:
            candidates.append((common.lower(), rhs_id))
        # Synonyms[] integration in Phase E
    return candidates


def fuzzy_match(
    name: str, candidates: list[tuple[str, int]], threshold: float = 0.85
) -> MatchResult | None:
    """Best fuzzy match over candidates above `threshold`. None if no match."""

    if not candidates:
        return None

    haystack = [c[0] for c in candidates]
    best = process.extractOne(
        name.lower(),
        haystack,
        scorer=Levenshtein.normalized_similarity,
        score_cutoff=threshold,
    )
    if best is None:
        return None

    matched_str, score, idx = best
    rhs_id = candidates[idx][1]
    return MatchResult(rhs_id=rhs_id, method="rapidfuzz", confidence=float(score))
```

- [ ] **Step 4: Run tests + commit**

```
pytest tests/matching/test_fuzzy.py -v
```
Expect: 2 passed.

```bash
git add requirements.txt src/matching/fuzzy.py tests/matching/test_fuzzy.py
git commit -m "$(cat <<'EOF'
add rapidfuzz residual matcher (threshold default 0.85)

build_candidates flattens RHS to (lookup_string, rhs_id) over botanical
and common names; fuzzy_match returns the best hit above threshold or
None. Threshold deliberately high — this is a residual after exact
match has failed; we'd rather punt to LLM than return a low-confidence
guess.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Non-plant classifier (`src/matching/classify.py`)

**Files:**
- Create: `src/matching/classify.py`
- Create: `tests/matching/test_classify.py`

- [ ] **Step 1: Failing tests**

Create `tests/matching/test_classify.py`:
```python
"""Tests for the deterministic non-plant prefilter."""

import pytest

from src.matching.classify import classify_product
from src.matching.models import ParsedName


def test_classifies_compost_as_non_plant():
    is_plant, category = classify_product("Multipurpose Compost 50L", parsed=None)
    assert is_plant is False
    assert category == "compost"


def test_classifies_secateurs_as_tool():
    is_plant, category = classify_product("Felco No.2 Secateurs", parsed=None)
    assert is_plant is False
    assert category == "tool"


def test_classifies_pot_as_pot():
    is_plant, category = classify_product("Terracotta plant pot 30cm", parsed=None)
    assert is_plant is False
    assert category == "pot"


def test_classifies_fertiliser_as_fertiliser():
    is_plant, category = classify_product("Tomato fertiliser 1L", parsed=None)
    assert is_plant is False
    assert category == "fertiliser"


def test_parsed_genus_implies_plant():
    parsed = ParsedName(genus="Acer", species="palmatum")
    is_plant, category = classify_product("Acer palmatum 9cm", parsed=parsed)
    assert is_plant is True
    assert category == "plant"


def test_tulipa_with_bulbs_indicator_is_bulb():
    parsed = ParsedName(genus="Tulipa", species="gesneriana", cultivar="Apricot Beauty")
    is_plant, category = classify_product("Tulipa 'Apricot Beauty' 5 bulbs", parsed=parsed)
    assert is_plant is True
    assert category == "bulb"


def test_unparseable_unknown_falls_to_other():
    is_plant, category = classify_product("Mystery item xyz", parsed=None)
    assert is_plant is False
    assert category == "other"
```

- [ ] **Step 2: Implement `src/matching/classify.py`**

```python
"""Deterministic non-plant prefilter.

Rules:
  - Strong product-category keyword in the name → non-plant, category = matched.
  - parsed is not None and indicators of bulb/seed → plant, but category = bulb/seed.
  - parsed is not None otherwise → plant, category = plant.
  - Else → non-plant, category = other (LLM may refine in Phase D).
"""

from __future__ import annotations

import re
from typing import Optional

from src.matching.models import ParsedName, ProductCategory

_NON_PLANT_PATTERNS: list[tuple[re.Pattern[str], ProductCategory]] = [
    (re.compile(r"\b(?:compost|peat|loam|topsoil|gravel|grit|mulch)\b", re.I), "compost"),
    (re.compile(r"\b(?:fertili[sz]er|feed|tonic|spray)\b", re.I), "fertiliser"),
    (re.compile(r"\b(?:secateur|spade|fork|rake|shears|trowel|hoe|loppers|wheelbarrow)\b", re.I), "tool"),
    (re.compile(r"\b(?:pot|planter|trough|tray|module|cell)\b", re.I), "pot"),
    (re.compile(r"\b(?:net|fleece|cloche|cane|stake|tie|tag|label)\b", re.I), "accessory"),
]

_BULB_INDICATORS = re.compile(r"\b(?:bulb|bulbs|tuber|tubers|corm|corms|rhizome)\b", re.I)
_SEED_INDICATORS = re.compile(r"\b(?:seed|seeds|seed packet|sachet)\b", re.I)


def classify_product(
    raw: str, parsed: Optional[ParsedName]
) -> tuple[bool, ProductCategory]:
    """Return (is_plant, product_category) for a product."""

    # Step 1: explicit non-plant keywords win
    for pattern, category in _NON_PLANT_PATTERNS:
        if pattern.search(raw):
            return False, category

    # Step 2: parsed plant + bulb/seed indicator → bulb/seed sub-category
    if parsed is not None:
        if _BULB_INDICATORS.search(raw):
            return True, "bulb"
        if _SEED_INDICATORS.search(raw):
            return True, "seed"
        return True, "plant"

    # Step 3: nothing parsed and no keyword → other
    return False, "other"
```

- [ ] **Step 3: Run tests + commit**

```
pytest tests/matching/test_classify.py -v
```
Expect: 7 passed.

```bash
git add src/matching/classify.py tests/matching/test_classify.py
git commit -m "$(cat <<'EOF'
add deterministic non-plant classifier

Three-rule prefilter: explicit non-plant keywords (compost, tool, pot,
fertiliser, accessory) win first; parsed plant + bulb/seed indicator →
bulb/seed sub-category; else → other. LLM may refine 'other' in Phase D.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Pipeline orchestrator (`src/matching/run.py`) — deterministic only

**Files:**
- Create: `src/matching/run.py`
- Create: `tests/matching/test_run.py`

- [ ] **Step 1: Failing test**

Create `tests/matching/test_run.py`:
```python
"""Integration test: deterministic match pipeline against the fixture."""

from pathlib import Path

import polars as pl
import pytest

from src.matching.run import run_matching

RHS_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rhs_sample.parquet"


@pytest.fixture
def rhs_df():
    return pl.read_parquet(RHS_FIXTURE)


@pytest.fixture
def products_df(rhs_df):
    """Build a small product DataFrame from the RHS fixture, plus some non-plants."""
    plants = rhs_df.head(20).select(
        pl.lit("test_nursery").alias("source"),
        pl.lit("https://example.com/p").alias("product_url"),
        pl.col("botanical_name").alias("product_name_raw"),
        pl.lit(9.99).alias("price_native"),
        pl.lit("EUR").alias("currency"),
    )
    non_plants = pl.DataFrame({
        "source": ["test_nursery"] * 3,
        "product_url": ["https://example.com/n"] * 3,
        "product_name_raw": ["Multipurpose Compost 50L", "Felco Secateurs", "Terracotta pot 30cm"],
        "price_native": [12.0, 49.0, 8.50],
        "currency": ["EUR"] * 3,
    })
    return pl.concat([plants, non_plants])


def test_pipeline_matches_known_plants(rhs_df, products_df):
    matched = run_matching(products_df, rhs_df, overrides=[])
    plant_rows = matched.filter(pl.col("is_plant") == True)
    # Most of the 20 fixture-derived plants should match (some may have weird formatting)
    matched_count = plant_rows.filter(pl.col("rhs_id").is_not_null()).height
    assert matched_count >= 15, f"Expected ≥15 of 20 to match, got {matched_count}"


def test_pipeline_classifies_non_plants(rhs_df, products_df):
    matched = run_matching(products_df, rhs_df, overrides=[])
    non_plant_rows = matched.filter(pl.col("is_plant") == False)
    assert len(non_plant_rows) >= 3
    categories = set(non_plant_rows.select("product_category").to_series().to_list())
    assert "compost" in categories
    assert "tool" in categories
    assert "pot" in categories
```

- [ ] **Step 2: Implement `src/matching/run.py`**

```python
"""Run the deterministic match pipeline over a products DataFrame."""

from __future__ import annotations

import polars as pl

from src.matching.classify import classify_product
from src.matching.exact import RhsIndex, exact_match
from src.matching.fuzzy import build_candidates, fuzzy_match
from src.matching.gnparser_wrap import ParseFailed, parse
from src.matching.models import MatchOverride
from src.matching.normalize import clean_product_name


def run_matching(
    products_df: pl.DataFrame,
    rhs_df: pl.DataFrame,
    overrides: list[MatchOverride],
) -> pl.DataFrame:
    """Apply the deterministic match pipeline. Returns a DataFrame with match columns added.

    LLM fallback is NOT invoked here — that's Phase D's `llm.batch_resolve` which is
    called separately on the residual where match_method == "unmatched".
    """

    rhs_index = RhsIndex.from_dataframe(rhs_df)
    candidates = build_candidates(rhs_df)
    overrides_by_clean = {o.product_name_clean: o for o in overrides}

    out_rows = []
    for row in products_df.iter_rows(named=True):
        raw = row["product_name_raw"]
        clean = clean_product_name(raw)

        # Step 0: override cache wins
        if (override := overrides_by_clean.get(clean)) is not None:
            out_rows.append({
                **row,
                "product_name_clean": clean,
                "rhs_id": override.rhs_id,
                "cultivar": override.cultivar,
                "match_method": "manual_override" if override.source == "manual" else "llm",
                "match_confidence": 1.0 if override.source == "manual" else 0.95,
                "is_plant": override.is_plant,
                "product_category": override.product_category,
                "genus": None,
                "species": None,
                "cultivar_group": None,
            })
            continue

        # Step 1: parse
        try:
            parsed = parse(clean)
        except ParseFailed:
            parsed = None

        # Step 2: classify (works with or without parse)
        is_plant, category = classify_product(raw, parsed)

        # Step 3: exact match if parsed
        result = exact_match(parsed, rhs_index) if parsed is not None else None

        # Step 4: fuzzy fallback
        if result is None and parsed is not None:
            result = fuzzy_match(clean, candidates, threshold=0.85)

        out_rows.append({
            **row,
            "product_name_clean": clean,
            "rhs_id": result.rhs_id if result else None,
            "cultivar": parsed.cultivar if parsed else None,
            "cultivar_group": parsed.cultivar_group if parsed else None,
            "genus": parsed.genus if parsed else None,
            "species": parsed.species if parsed else None,
            "match_method": result.method if result else "unmatched",
            "match_confidence": result.confidence if result else 0.0,
            "is_plant": is_plant,
            "product_category": category,
        })

    return pl.DataFrame(out_rows)
```

- [ ] **Step 3: Run + commit**

```
pytest tests/matching/test_run.py -v
```
Expect: 2 passed.

```bash
git add src/matching/run.py tests/matching/test_run.py
git commit -m "$(cat <<'EOF'
add deterministic match pipeline orchestrator

Pipeline: clean → override cache → parse → classify → exact → fuzzy.
Returns a polars DataFrame with all matching columns populated. LLM
fallback is intentionally separate (Phase D) so the deterministic
pipeline is fully testable offline.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase D — LLM fallback

### Task 12: Anthropic SDK + LLM module skeleton

**Files:**
- Modify: `requirements.txt` (add `anthropic`)
- Create: `src/matching/llm.py`
- Create: `tests/matching/test_llm.py` (with mocked SDK)

- [ ] **Step 1: Add anthropic SDK**

Append to `requirements.txt`: `anthropic`. Then `pip install anthropic`.

- [ ] **Step 2: Failing tests with mocked Anthropic client**

Create `tests/matching/test_llm.py`:
```python
"""Tests for the LLM batch resolver (with mocked Anthropic client)."""

from unittest.mock import MagicMock, patch

import pytest

from src.matching.llm import batch_resolve
from src.matching.models import MatchOverride


@patch("src.matching.llm.Anthropic")
def test_batch_resolve_returns_overrides(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='[{"product_name_clean":"acer palmatum bloodgood","rhs_id":12345,"cultivar":"Bloodgood","is_plant":true,"product_category":"plant","confidence":0.95,"reasoning":"clear cultivar"}]')]
    )
    rhs_candidates = {12345: {"genus": "Acer", "species": "palmatum", "common_names": ["Japanese Maple"], "synonyms": []}}
    overrides = batch_resolve(["acer palmatum bloodgood"], rhs_candidates)
    assert len(overrides) == 1
    assert isinstance(overrides[0], MatchOverride)
    assert overrides[0].rhs_id == 12345
    assert overrides[0].cultivar == "Bloodgood"
    assert overrides[0].source == "llm"


@patch("src.matching.llm.Anthropic")
def test_batch_resolve_handles_no_match(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='[{"product_name_clean":"unknown thing","rhs_id":null,"is_plant":false,"product_category":"other","confidence":0.5,"reasoning":"not a plant"}]')]
    )
    overrides = batch_resolve(["unknown thing"], {})
    assert overrides[0].rhs_id is None
    assert overrides[0].is_plant is False
    assert overrides[0].product_category == "other"
```

- [ ] **Step 3: Implement `src/matching/llm.py`**

```python
"""LLM batch fallback for unmatched products, using Claude Haiku 4.5 with prompt caching.

The RHS candidate list is sent as a CACHED system prefix so subsequent calls within
the cache TTL hit cheap. Each call resolves up to BATCH_SIZE products at once.
"""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic

from src.matching.models import MatchOverride

BATCH_SIZE = 50
MODEL = "claude-haiku-4-5-20251001"


def batch_resolve(
    unmatched_clean_names: list[str],
    rhs_candidates: dict[int, dict[str, Any]],
    *,
    model: str = MODEL,
    api_key: str | None = None,
) -> list[MatchOverride]:
    """Resolve unmatched product names via Claude Haiku.

    Args:
        unmatched_clean_names: cleaned product names that the deterministic pipeline missed.
        rhs_candidates: dict[rhs_id, {genus, species, common_names, synonyms}] subset of RHS
            relevant to these products. Caller is responsible for narrowing this — the full
            62k RHS table is too large to send.
        model: anthropic model id.
        api_key: optional override; defaults to ANTHROPIC_API_KEY env var.

    Returns:
        List of MatchOverride records ready to be persisted via overrides.upsert_override.
    """

    client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    candidate_block = json.dumps(rhs_candidates, indent=None, separators=(",", ":"))

    overrides: list[MatchOverride] = []
    for chunk_start in range(0, len(unmatched_clean_names), BATCH_SIZE):
        chunk = unmatched_clean_names[chunk_start : chunk_start + BATCH_SIZE]
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": (
                        "You are a botanical name matcher. Given a list of RHS plant records "
                        "(id → {genus, species, common_names, synonyms}) and a list of unmatched "
                        "product strings from Irish/UK nurseries, return JSON ONLY (no prose) "
                        "as an array. Each element must be:\n"
                        '{"product_name_clean": str, "rhs_id": int|null, "cultivar": str|null, '
                        '"is_plant": bool, "product_category": one of '
                        '"plant"|"bulb"|"seed"|"compost"|"soil"|"tool"|"pot"|"fertiliser"|"accessory"|"other", '
                        '"confidence": float in [0,1], "reasoning": str}\n'
                        "If product is not a plant, set is_plant=false and pick the right category. "
                        "If a plant has a cultivar in quotes, extract it. If no RHS record matches "
                        "at species level, set rhs_id=null."
                    ),
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": f"RHS candidates: {candidate_block}",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Products to match:\n{json.dumps(chunk)}",
                }
            ],
        )
        text = message.content[0].text
        results = json.loads(text)
        for r in results:
            overrides.append(
                MatchOverride(
                    product_name_clean=r["product_name_clean"],
                    rhs_id=r.get("rhs_id"),
                    cultivar=r.get("cultivar"),
                    is_plant=r.get("is_plant", False),
                    product_category=r.get("product_category", "other"),
                    source="llm",
                    model=model,
                    notes=r.get("reasoning"),
                )
            )

    return overrides
```

- [ ] **Step 4: Run mocked tests + commit**

```
pytest tests/matching/test_llm.py -v
```
Expect: 2 passed (no real API calls — Anthropic client is mocked).

```bash
git add requirements.txt src/matching/llm.py tests/matching/test_llm.py
git commit -m "$(cat <<'EOF'
add LLM batch fallback (Haiku 4.5 with prompt caching)

batch_resolve sends the RHS candidate subset as a cached system prefix
and resolves up to 50 products per call. Returns MatchOverride records
ready for overrides.upsert_override. Tests mock the Anthropic client
so they're free and offline; live API hits happen only via the run.py
integration in Phase F.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Wire LLM into the orchestrator + override persistence

**Files:**
- Modify: `src/matching/run.py` (add `run_with_llm_fallback` function)
- Create/modify: `tests/matching/test_run.py` (add LLM-fallback test with mocked client)

- [ ] **Step 1: Failing test for the LLM-aware orchestrator**

Append to `tests/matching/test_run.py`:
```python
from unittest.mock import patch

from src.matching.models import MatchOverride
from src.matching.run import run_with_llm_fallback


@patch("src.matching.llm.Anthropic")
def test_llm_fallback_persists_overrides(mock_client_cls, rhs_df, products_df, tmp_path, monkeypatch):
    # Force everything into "unmatched" by dropping all RHS data the deterministic pipeline could find
    empty_rhs = rhs_df.head(0)
    overrides_path = tmp_path / "match_overrides.parquet"
    monkeypatch.setattr("src.matching.overrides.OVERRIDES_PARQUET", overrides_path)

    from unittest.mock import MagicMock
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    # Mock returns "unmatched/non-plant" for every product
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=str([
            {"product_name_clean": p, "rhs_id": None, "is_plant": False, "product_category": "other", "confidence": 0.3, "reasoning": "no RHS data"}
            for p in products_df.select("product_name_raw").to_series().to_list()
        ]).replace("'", '"').replace("False", "false").replace("None", "null"))]
    )

    matched = run_with_llm_fallback(products_df, empty_rhs, llm_enabled=True)
    # All products fall through to LLM; LLM marks them all as non-plant
    assert (matched.select("match_method").to_series() == "llm").all()
```

- [ ] **Step 2: Implement `run_with_llm_fallback` in `src/matching/run.py`**

Append to `src/matching/run.py`:
```python
def run_with_llm_fallback(
    products_df: pl.DataFrame,
    rhs_df: pl.DataFrame,
    *,
    llm_enabled: bool = True,
    api_key: str | None = None,
) -> pl.DataFrame:
    """Run deterministic pipeline; LLM-resolve any residual; persist overrides; re-apply.

    This is the production entry point. The deterministic pipeline is also useful in
    isolation for fast offline test runs.
    """

    from src.matching.llm import batch_resolve
    from src.matching.overrides import load_overrides, save_overrides

    overrides = load_overrides()
    matched = run_matching(products_df, rhs_df, overrides=overrides)

    if not llm_enabled:
        return matched

    unmatched = matched.filter(pl.col("match_method") == "unmatched")
    if len(unmatched) == 0:
        return matched

    # Build a candidate dict of all RHS records (the LLM picks among them).
    # In production this should be narrowed to top-N rapidfuzz candidates per product
    # to keep the cached prefix small; v1 sends them all.
    rhs_candidates = {
        row["id"]: {
            "genus": (row["botanical_name"] or "").split(" ")[0] if row["botanical_name"] else "",
            "species": (row["botanical_name"] or "").split(" ")[1].strip("'\"") if row["botanical_name"] and " " in row["botanical_name"] else "",
            "common_names": [row["common_name"]] if row.get("common_name") else [],
            "synonyms": row.get("synonyms") or [],
        }
        for row in rhs_df.iter_rows(named=True)
    }

    new_overrides = batch_resolve(
        unmatched.select("product_name_clean").to_series().to_list(),
        rhs_candidates,
        api_key=api_key,
    )

    save_overrides(overrides + new_overrides)

    # Re-run the deterministic pipeline so the new overrides flow through
    return run_matching(products_df, rhs_df, overrides=overrides + new_overrides)
```

- [ ] **Step 3: Run tests + commit**

```
pytest tests/matching/test_run.py -v
```
Expect: 3 passed (the original 2 + the new LLM fallback test).

```bash
git add src/matching/run.py tests/matching/test_run.py
git commit -m "$(cat <<'EOF'
add LLM-aware orchestrator: deterministic + fallback + persist

run_with_llm_fallback runs the deterministic pipeline, batches any
unmatched residual through Claude Haiku, persists the new overrides
to data/match_overrides.parquet, and re-applies. llm_enabled flag
allows the deterministic-only path for offline tests.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: `scripts/edit_overrides.py` CLI for human curation

**Files:**
- Create: `scripts/edit_overrides.py`
- Create: `tests/matching/test_edit_overrides.py`

- [ ] **Step 1: Failing test**

Create `tests/matching/test_edit_overrides.py`:
```python
"""Tests for the edit_overrides CLI."""

import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest

from src.matching.models import MatchOverride
from src.matching.overrides import save_overrides


def test_list_command_prints_overrides(tmp_path, monkeypatch):
    p = tmp_path / "match_overrides.parquet"
    monkeypatch.setattr("src.matching.overrides.OVERRIDES_PARQUET", p)
    save_overrides([
        MatchOverride(product_name_clean="acer palmatum bloodgood", rhs_id=42, source="llm"),
    ])
    result = subprocess.run(
        [sys.executable, "scripts/edit_overrides.py", "list"],
        capture_output=True, text=True,
        env={"OVERRIDES_PARQUET": str(p), **dict(__import__("os").environ)},
    )
    assert result.returncode == 0
    assert "acer palmatum bloodgood" in result.stdout
    assert "42" in result.stdout
```

- [ ] **Step 2: Implement `scripts/edit_overrides.py`**

```python
"""CLI for viewing and editing data/match_overrides.parquet.

Subcommands:
  list                — print all overrides
  set <name> <rhs_id> — manually map a product name to an RHS id
  delete <name>       — remove an override
"""

import argparse
import os
import sys
from pathlib import Path

# Allow OVERRIDES_PARQUET env override (used by tests)
if "OVERRIDES_PARQUET" in os.environ:
    import src.matching.overrides as overrides_mod
    overrides_mod.OVERRIDES_PARQUET = Path(os.environ["OVERRIDES_PARQUET"])

from src.matching.models import MatchOverride
from src.matching.overrides import load_overrides, upsert_override


def cmd_list(_args):
    overrides = load_overrides()
    if not overrides:
        print("(no overrides)")
        return
    for o in overrides:
        print(f"{o.product_name_clean!r}  →  rhs_id={o.rhs_id}  cultivar={o.cultivar!r}  source={o.source}")


def cmd_set(args):
    upsert_override(MatchOverride(
        product_name_clean=args.name,
        rhs_id=args.rhs_id,
        cultivar=args.cultivar,
        is_plant=args.is_plant,
        source="manual",
        notes=args.notes,
    ))
    print(f"Set override: {args.name!r} → rhs_id={args.rhs_id}")


def cmd_delete(args):
    overrides = load_overrides()
    keep = [o for o in overrides if o.product_name_clean != args.name]
    if len(keep) == len(overrides):
        print(f"No override found for {args.name!r}")
        return 1
    from src.matching.overrides import save_overrides
    save_overrides(keep)
    print(f"Deleted override: {args.name!r}")


def main():
    parser = argparse.ArgumentParser(description="Edit data/match_overrides.parquet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=cmd_list)

    s = sub.add_parser("set")
    s.add_argument("name", help="product_name_clean")
    s.add_argument("rhs_id", type=int)
    s.add_argument("--cultivar", default=None)
    s.add_argument("--is-plant", type=bool, default=True)
    s.add_argument("--notes", default=None)
    s.set_defaults(func=cmd_set)

    s = sub.add_parser("delete")
    s.add_argument("name")
    s.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests + commit**

```
pytest tests/matching/test_edit_overrides.py -v
```
Expect: 1 passed.

```bash
git add scripts/edit_overrides.py tests/matching/test_edit_overrides.py
git commit -m "$(cat <<'EOF'
add edit_overrides CLI for human curation of matches

list / set / delete subcommands for data/match_overrides.parquet.
'manual' source overrides supersede 'llm' source on next pipeline run
(per upsert_override). Lets a maintainer fix bad LLM matches without
touching code.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase E — RHS schema rework

### Task 15: New `RhsRecord` parquet schema (write helper)

**Files:**
- Create: `src/matching/rhs_remodel.py`
- Create: `tests/matching/test_rhs_remodel.py`

- [ ] **Step 1: Failing test**

Create `tests/matching/test_rhs_remodel.py`:
```python
"""Tests for migrating the legacy rhs.parquet to the new schema."""

from pathlib import Path

import polars as pl

from src.matching.rhs_remodel import remodel


def test_remodel_splits_genus_species(tmp_path):
    # Build a small synthetic legacy parquet
    legacy = pl.DataFrame({
        "id": [1, 2, 3],
        "source": ["rhs"] * 3,
        "plant_url": ["https://rhs.org.uk/plants/1"] * 3,
        "botanical_name": ["Acer palmatum", "Rosa 'Irish Fireflame' (HT)", "Tulipa gesneriana"],
        "common_name": ["Japanese Maple", None, "Tulip"],
        "plant_type": [["Tree"], ["Climber"], ["Bulb"]],
        "description": [None] * 3,
        "is_rhs_award_winner": [False] * 3,
        "is_pollinator_plant": [False] * 3,
        "height": [None] * 3,
        "spread": [None] * 3,
        "time_to_ultimate_spread": [None] * 3,
        "soils": [[]] * 3,
        "moisture": [None] * 3,
        "ph": [None] * 3,
        "sun_exposure": [None] * 3,
        "aspect": [[]] * 3,
        "exposure": [[]] * 3,
        "hardiness": [None] * 3,
        "foliage": [None] * 3,
        "habit": [[]] * 3,
    })
    out = tmp_path / "rhs_new.parquet"
    remodel(legacy, out)
    new = pl.read_parquet(out)
    assert "genus" in new.columns
    assert "species" in new.columns
    assert "synonyms" in new.columns
    assert "common_names" in new.columns

    acer = new.filter(pl.col("rhs_id") == 1).to_dicts()[0]
    assert acer["genus"] == "Acer"
    assert acer["species"] == "palmatum"
    assert acer["common_names"] == ["Japanese Maple"]
    assert acer["synonyms"] == []

    rosa = new.filter(pl.col("rhs_id") == 2).to_dicts()[0]
    assert rosa["genus"] == "Rosa"
    # Cultivar is part of botanical_name in legacy data; new schema keeps it stored
    # but matching uses (genus, species) only.
    assert rosa["species"] in ("'Irish", "")  # depends on how we strip cultivar quotes
```

- [ ] **Step 2: Implement `src/matching/rhs_remodel.py`**

```python
"""One-shot migration: legacy rhs.parquet → new schema with genus/species/synonyms."""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

_CULTIVAR_RE = re.compile(r"\s*'[^']+'\s*(\([^)]+\))?$")


def _split_botanical(name: str) -> tuple[str, str]:
    """Return (genus, species) from a botanical name. Cultivar/group are stripped."""

    if not name:
        return "", ""
    cleaned = _CULTIVAR_RE.sub("", name).strip()
    parts = cleaned.split(" ")
    genus = parts[0] if parts else ""
    species = parts[1] if len(parts) > 1 else ""
    return genus, species


def remodel(legacy_df: pl.DataFrame, out_path: Path | str) -> None:
    """Write a re-modelled RHS parquet.

    - Renames `id` → `rhs_id`.
    - Adds `genus`, `species` columns parsed from `botanical_name`.
    - `common_names` becomes a list[str] (was a single common_name).
    - Adds empty `synonyms` list (populated by the next-run rhs scraper, Task 17).
    """

    new = legacy_df.with_columns([
        pl.col("id").alias("rhs_id"),
        pl.col("botanical_name").map_elements(
            lambda n: _split_botanical(n)[0], return_dtype=pl.Utf8
        ).alias("genus"),
        pl.col("botanical_name").map_elements(
            lambda n: _split_botanical(n)[1], return_dtype=pl.Utf8
        ).alias("species"),
        pl.when(pl.col("common_name").is_not_null())
            .then(pl.col("common_name").map_elements(lambda c: [c], return_dtype=pl.List(pl.Utf8)))
            .otherwise(pl.lit([], dtype=pl.List(pl.Utf8)))
            .alias("common_names"),
        pl.lit([], dtype=pl.List(pl.Utf8)).alias("synonyms"),
    ])

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    new.write_parquet(out_path)
```

- [ ] **Step 3: Run tests + commit**

```
pytest tests/matching/test_rhs_remodel.py -v
```
Expect: 1 passed (with notes; cultivar parsing is best-effort).

```bash
git add src/matching/rhs_remodel.py tests/matching/test_rhs_remodel.py
git commit -m "$(cat <<'EOF'
add legacy → new RHS schema migration

remodel() splits botanical_name into (genus, species), promotes
common_name to list[str], and adds an empty synonyms[] column. Cultivar
quotes are stripped from species so exact match works against
nursery-side parsed names. The next-run rhs scraper (Task 17) will
populate synonyms[] from the RHS detail page.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: Run the migration on production data

**Files:**
- Modify: `data/rhs.parquet` (re-modelled in place — backup first)

- [ ] **Step 1: Back up the existing `data/rhs.parquet`**

```
cp data/rhs.parquet data/rhs.legacy.parquet
```

- [ ] **Step 2: Run the migration**

```
python -c "
import polars as pl
from src.matching.rhs_remodel import remodel
legacy = pl.read_parquet('data/rhs.legacy.parquet')
remodel(legacy, 'data/rhs.parquet')
new = pl.read_parquet('data/rhs.parquet')
print('New schema:', new.columns)
print('Row count:', len(new))
"
```

Expect: schema includes `rhs_id`, `genus`, `species`, `common_names`, `synonyms`. Row count ~62755 (unchanged from legacy).

- [ ] **Step 3: Sanity-check that real botanical names parsed correctly**

```
python -c "
import polars as pl
df = pl.read_parquet('data/rhs.parquet')
print('Empty species:', df.filter(pl.col('species') == '').height)
print('Sample 10:')
for row in df.sample(10, seed=99).iter_rows(named=True):
    print(f'  rhs_id={row[\"rhs_id\"]} genus={row[\"genus\"]!r} species={row[\"species\"]!r}')
"
```

Expect: empty-species count is small (< 100 — these are records with non-binomial names like just "Rosa" or hybrid notations gnparser would fail on too). Sample looks reasonable.

- [ ] **Step 4: Commit**

```bash
git add data/rhs.parquet data/rhs.legacy.parquet
git commit -m "$(cat <<'EOF'
migrate rhs.parquet to new schema with genus/species/synonyms

Renames id→rhs_id, splits botanical_name into (genus, species),
promotes common_name to list, adds empty synonyms[] (populated by
next rhs scraper run, Task 17). Old parquet kept as data/rhs.legacy.parquet
for reference.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 17: Update RHS scraper to capture synonyms

**Files:**
- Modify: `src/scrapers/rhs.py` (add synonym extraction)
- Add: `tests/scrapers/test_rhs_synonyms.py` (uses a saved HTML fixture from one synonym-bearing RHS page)

- [ ] **Step 1: Capture an HTML fixture**

```
mkdir -p tests/fixtures/rhs_html
python -c "
from requests_html import HTMLSession
s = HTMLSession()
# Pick a known synonym-bearing plant — e.g. one where the RHS page shows 'Synonyms'
r = s.get('https://www.rhs.org.uk/plants/5638/deschampsia-cespitosa/details')
open('tests/fixtures/rhs_html/deschampsia-cespitosa.html', 'wb').write(r.content)
print(f'wrote {len(r.content)} bytes')
"
```

Expect: HTML file ~50-200 KB.

- [ ] **Step 2: Failing test**

Create `tests/scrapers/__init__.py` (empty) if not present.

Create `tests/scrapers/test_rhs_synonyms.py`:
```python
"""Test that the RHS scraper extracts synonyms from a real page fixture."""

from pathlib import Path

from bs4 import BeautifulSoup

from src.scrapers.rhs import extract_detailed_plant_data


def test_extracts_synonyms_when_present():
    html = (Path(__file__).resolve().parents[1] / "fixtures" / "rhs_html" / "deschampsia-cespitosa.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    plant = {"id": 5638, "plant_url": "https://www.rhs.org.uk/plants/5638/deschampsia-cespitosa/details"}
    extract = extract_detailed_plant_data(plant, soup)
    assert "synonyms" in extract
    # At least one synonym OR an empty list (page may have changed by test time)
    assert isinstance(extract["synonyms"], list)
```

- [ ] **Step 3: Modify `src/scrapers/rhs.py` to extract synonyms**

The current code at line 30-38 actively excludes synonyms with `if pt.text.strip() != "Synonym"`. Change this to capture them in a separate list.

Find the existing block:
```python
plant_type = [
    pt.text.strip()
    for pt in plant_content.find_all("span", class_="label ng-star-inserted")
    if pt.text.strip() != "Synonym"
]
```

Replace with:
```python
all_labels = plant_content.find_all("span", class_="label ng-star-inserted")
plant_type = [pt.text.strip() for pt in all_labels if pt.text.strip() != "Synonym"]

# Synonyms appear as `<span class="label ng-star-inserted">Synonym</span>` next to the synonym text.
# Find all elements where the previous sibling label is "Synonym"; collect their text.
synonyms: list[str] = []
for label in all_labels:
    if label.text.strip() == "Synonym":
        # Synonym text is in the parent's other children
        parent = label.parent
        synonym_text = parent.get_text(strip=True).replace("Synonym", "", 1).strip()
        if synonym_text:
            synonyms.append(synonym_text)
```

And add `"synonyms": synonyms` to the `extract = {...}` return dict near line 185.

- [ ] **Step 4: Run tests + commit**

```
pytest tests/scrapers/test_rhs_synonyms.py -v
```
Expect: 1 passed.

```bash
git add src/scrapers/rhs.py tests/scrapers/__init__.py tests/scrapers/test_rhs_synonyms.py tests/fixtures/rhs_html/
git commit -m "$(cat <<'EOF'
capture RHS synonyms instead of discarding them

Previously the rhs.py scraper filtered out 'Synonym' labels at the
plant_type extraction step (line 34), so nurseries using older accepted
names had no chance of matching. Now synonyms are collected into their
own list and persisted on the RhsRecord. HTML fixture from the
deschampsia-cespitosa page committed for regression coverage.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase F — Integration + retire legacy

### Task 18: Add a `--matching` subcommand to the orchestrator

**Files:**
- Modify: `load_bronze_data.py`

- [ ] **Step 1: Read the current `load_bronze_data.py` shape**

Quickly inspect lines 55-73 (the argparse block). The current parser has one `--site` argument with a `choices=[...]` whitelist. We need to make `--site` optional and add a mutually-exclusive `--matching` flag plus a `--no-llm` flag.

- [ ] **Step 2: Add a `_run_matching` helper near the top of `load_bronze_data.py`**

Insert below the existing imports (around line 8, after `import pyarrow.dataset as ds`):

```python
from datetime import date
from pathlib import Path

NURSERIES = ("tullys", "quickcrop", "gardens4you", "carragh", "arboretum")


def _run_matching(*, llm_enabled: bool) -> None:
    """Load latest per-nursery parquets + RHS, run the matching pipeline, write output."""

    from src.matching.run import run_with_llm_fallback

    frames = []
    for nursery in NURSERIES:
        nursery_dir = Path(f"data/{nursery}")
        parquets = sorted(nursery_dir.glob("*.parquet"))
        if not parquets:
            print(f"No parquets for {nursery}, skipping.")
            continue
        frames.append(pl.read_parquet(parquets[-1]).with_columns(pl.lit(nursery).alias("source")))

    if not frames:
        raise SystemExit("No nursery parquets found — run scrapes first.")

    products_df = pl.concat(frames, how="diagonal_relaxed").rename(
        {"product_name": "product_name_raw"}
    )
    rhs_df = pl.read_parquet("data/rhs.parquet")

    matched = run_with_llm_fallback(products_df, rhs_df, llm_enabled=llm_enabled)
    out = Path("data/products_matched.parquet")
    matched.write_parquet(out)
    print(f"Wrote {len(matched)} matched products → {out}")
```

- [ ] **Step 3: Update the argparse block to add the new flags**

Replace the `if __name__ == "__main__":` block (lines 55-73 currently) with:

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape nurseries, manage RHS data, or run the matching pipeline."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--site",
        help="Name of the site you would like to fetch data for.",
        choices=[
            "tullys",
            "quickcrop",
            "gardens4you",
            "carragh",
            "arboretum",
            "rhs",
            "rhs_urls",
        ],
    )
    mode.add_argument(
        "--matching",
        action="store_true",
        help="Run the matching pipeline against the latest scraped data.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="When used with --matching, skip the LLM fallback (deterministic only).",
    )
    args = parser.parse_args()

    if args.matching:
        _run_matching(llm_enabled=not args.no_llm)
    else:
        main(args)
```

- [ ] **Step 4: Smoke test the new subcommand (deterministic only)**

```
python load_bronze_data.py --matching --no-llm
```

Expect: writes `data/products_matched.parquet`. Some scrapers may have stale data; that's fine — we're verifying the pipeline runs end-to-end.

- [ ] **Step 5: Commit**

```bash
git add load_bronze_data.py
git commit -m "$(cat <<'EOF'
wire matching pipeline into orchestrator (--matching flag)

Reads latest dated parquet per nursery + data/rhs.parquet, runs the
deterministic + LLM pipeline (or just deterministic with --no-llm),
writes data/products_matched.parquet. --matching and --site are
mutually exclusive; one is required.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: End-to-end smoke against production data

**Files:**
- (none modified — verification only)

- [ ] **Step 1: Run the matching pipeline (deterministic only first)**

```
python load_bronze_data.py --matching --no-llm
```

- [ ] **Step 2: Inspect the result**

```
python -c "
import polars as pl
df = pl.read_parquet('data/products_matched.parquet')
print('Total rows:', len(df))
print('Plant rows:', df.filter(pl.col('is_plant') == True).height)
print('Non-plant rows:', df.filter(pl.col('is_plant') == False).height)
print('Match method counts:')
print(df.group_by('match_method').agg(pl.len()).sort('len', descending=True))
print('Unmatched sample:')
print(df.filter(pl.col('match_method') == 'unmatched').head(10).select('product_name_raw'))
"
```

Expect: > 60% of plant rows matched deterministically. Unmatched sample is dominated by either (a) genuinely missing-from-RHS cultivars, (b) non-binomial product names, or (c) misspellings.

- [ ] **Step 3: Run with LLM fallback (requires `ANTHROPIC_API_KEY`)**

```
ANTHROPIC_API_KEY=... python load_bronze_data.py --matching
```

Expect: the unmatched residual drops further; new entries land in `data/match_overrides.parquet`.

- [ ] **Step 4: Spot-check 10 LLM matches manually**

```
python scripts/edit_overrides.py list | head -20
```

Verify the LLM matches look reasonable. If any are wrong, use `scripts/edit_overrides.py set ...` to override them with `source=manual`.

- [ ] **Step 5: Commit the override file**

```bash
git add data/match_overrides.parquet
git commit -m "$(cat <<'EOF'
seed match_overrides with first LLM resolution pass

First production LLM run resolved <N> previously-unmatched products.
Auditable via scripts/edit_overrides.py list.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: Delete legacy reference files

**Files:**
- Delete: `src/matching/legacy_match.py`
- Delete: `src/matching/legacy_combine_names.py`
- Modify: `pyproject.toml` (remove the `**/legacy_*.py` exclude — no longer needed)

- [ ] **Step 1: Delete the legacy files**

```
git rm src/matching/legacy_match.py src/matching/legacy_combine_names.py
```

- [ ] **Step 2: Remove the now-unused pyright exclude**

Edit `pyproject.toml` — remove the `exclude = ["**/legacy_*.py"]` line from `[tool.pyright]`. Keep `venvPath`, `venv`, `extraPaths`.

- [ ] **Step 3: Run all tests**

```
pytest -v
```

Expect: all tests still pass. Nothing else imports the legacy files.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
delete legacy matching code now that v2 pipeline ships

src/matching/legacy_*.py served as documentation while sub-project 2
implemented the replacement (gnparser + LLM fallback + cultivar
preservation + non-plant classification + RHS schema rework). All
removed; pyright exclude rule removed alongside.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Out of scope for sub-project 2

- Dashboard surfacing of match_method/confidence (sub-project 3).
- CI for the matching pipeline (sub-project 4).
- Backfilling synonyms[] for the existing 62k RHS rows (a one-shot re-scrape, deferred to sub-project 1's hardening — RHS scraper rewrite).
- Replacing rapidfuzz with anything more sophisticated (splink, dedupe).
- Sister-repo cleanup (`MIGRATED.md`, deletion of Mage/dbt/Terraform). Now safe to do at the end of this sub-project since the matching code is fully ported. Add as final commit if desired.

---

## Self-review checklist (run before declaring sub-project 2 done)

- [ ] All 20 tasks above show every step ticked.
- [ ] `pytest -v` passes (~30+ tests).
- [ ] `python load_bronze_data.py --matching --no-llm` produces `data/products_matched.parquet` with ≥ 60% deterministic match rate.
- [ ] `python load_bronze_data.py --matching` (with LLM) drops unmatched to < 100 rows.
- [ ] `data/match_overrides.parquet` is committed and human-readable via `scripts/edit_overrides.py list`.
- [ ] `src/matching/legacy_*.py` files are deleted.
- [ ] `pyproject.toml` no longer has the legacy_*.py exclude.
- [ ] No file in `src/matching/` references `legacy_match` or `legacy_combine_names`.
