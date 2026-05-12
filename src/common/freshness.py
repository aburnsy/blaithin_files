"""Freshness gate for nightly scrapes — decides whether a source needs scraping."""

import datetime
from pathlib import Path

import pyarrow.parquet as pq


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

    source_dir = data_root / source
    if not source_dir.is_dir():
        return True, f"RUN {source}: no data directory at {source_dir}"

    parquets = sorted(source_dir.glob("*.parquet"))
    if not parquets:
        return True, f"RUN {source}: no parquet files in {source_dir}"

    newest = parquets[-1]

    try:
        file_date = datetime.date.fromisoformat(newest.stem)
    except ValueError:
        return True, f"RUN {source}: newest file {newest.name} has unparseable date"

    try:
        num_rows = pq.ParquetFile(newest).metadata.num_rows
    except Exception as exc:
        return True, f"RUN {source}: could not read {newest.name} ({exc})"

    if num_rows < 1:
        return True, f"RUN {source}: newest parquet {newest.name} has 0 rows"

    age_days = (today - file_date).days
    if age_days < max_age_days:
        return False, f"SKIP {source}: fresh parquet {file_date.isoformat()} (age {age_days}d)"

    return (
        True,
        f"RUN {source}: stale parquet {file_date.isoformat()} (age {age_days}d >= {max_age_days}d)",
    )
