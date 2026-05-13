"""Freshness gate for nightly scrapes — decides whether a source needs scraping."""

import datetime
from pathlib import Path

import pyarrow.parquet as pq


PARQUET_NAME = "data.parquet"


def should_scrape(
    source: str,
    *,
    max_age_days: int = 30,
    force: bool = False,
    today: datetime.date | None = None,
    data_root: Path = Path("data"),
) -> tuple[bool, str]:
    """Return (run, reason). reason is a one-line log message."""
    if force:
        return True, "FORCE: bypassing freshness gate"

    if today is None:
        today = datetime.date.today()

    parquet = data_root / source / PARQUET_NAME
    if not parquet.is_file():
        return True, f"RUN {source}: no parquet at {parquet}"

    try:
        num_rows = pq.ParquetFile(parquet).metadata.num_rows
    except Exception as exc:
        return True, f"RUN {source}: could not read {parquet.name} ({exc})"

    if num_rows < 1:
        return True, f"RUN {source}: parquet {parquet.name} has 0 rows"

    mtime = datetime.date.fromtimestamp(parquet.stat().st_mtime)
    age_days = (today - mtime).days
    if age_days < max_age_days:
        return False, f"SKIP {source}: fresh parquet (mtime {mtime.isoformat()}, age {age_days}d)"

    return (
        True,
        f"RUN {source}: stale parquet (mtime {mtime.isoformat()}, age {age_days}d >= {max_age_days}d)",
    )
