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
        print(f"Refreshed FX rates -> {FX_PARQUET}")
