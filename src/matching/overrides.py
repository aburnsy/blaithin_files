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
