"""One-shot migration: legacy rhs.parquet -> new schema with genus/species/synonyms."""

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

    - Renames `id` -> `rhs_id`.
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
