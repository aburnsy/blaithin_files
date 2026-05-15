"""Read/write the human-auditable cache of LLM and manual match decisions.

Writes are atomic: the parquet is staged to ``<path>.tmp`` and ``os.replace``d
into the final location. A crash mid-write cannot truncate the live file.
"""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl

from src.matching.models import MatchOverride

OVERRIDES_PARQUET = Path(__file__).resolve().parents[2] / "data" / "match_overrides.parquet"

_EMPTY_SCHEMA = {
    "product_name_clean": pl.Utf8,
    "rhs_id": pl.Int64,
    "cultivar": pl.Utf8,
    "is_plant": pl.Boolean,
    "product_category": pl.Utf8,
    "source": pl.Utf8,
    "model": pl.Utf8,
    "created_at": pl.Datetime,
    "notes": pl.Utf8,
}


def load_overrides() -> list[MatchOverride]:
    """Load all overrides from the parquet. Empty list if file missing."""

    if not OVERRIDES_PARQUET.exists():
        return []
    df = pl.read_parquet(OVERRIDES_PARQUET)
    return [MatchOverride.model_validate(row) for row in df.iter_rows(named=True)]


def save_overrides(overrides: list[MatchOverride]) -> None:
    """Atomically overwrite the overrides parquet with the given list.

    Writes to ``<OVERRIDES_PARQUET>.tmp`` first, then ``os.replace`` swaps it
    into place. If the process crashes mid-``write_parquet``, the live file is
    untouched; the dangling ``.tmp`` is harmless and overwritten on next save.
    """

    OVERRIDES_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    tmp = OVERRIDES_PARQUET.with_suffix(".parquet.tmp")

    if not overrides:
        pl.DataFrame(schema=_EMPTY_SCHEMA).write_parquet(tmp)
    else:
        df = pl.DataFrame([o.model_dump() for o in overrides])
        df.write_parquet(tmp)

    os.replace(tmp, OVERRIDES_PARQUET)


def upsert_override(override: MatchOverride) -> None:
    """Insert or replace an override (keyed on product_name_clean)."""

    existing = load_overrides()
    others = [o for o in existing if o.product_name_clean != override.product_name_clean]
    save_overrides(others + [override])
