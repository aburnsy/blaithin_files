"""Tests for the scrape freshness gate."""

import datetime
import os
from pathlib import Path

import polars as pl

from src.common.freshness import PARQUET_NAME, should_scrape


TODAY = datetime.date(2026, 5, 12)


def _write_parquet(path: Path, *, rows: int = 1, mtime_date: datetime.date | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rows == 0:
        df = pl.DataFrame({"product_name": pl.Series([], dtype=pl.Utf8)})
    else:
        df = pl.DataFrame({"product_name": [f"item-{i}" for i in range(rows)]})
    df.write_parquet(path)
    if mtime_date is not None:
        ts = datetime.datetime.combine(mtime_date, datetime.time(12, 0)).timestamp()
        os.utime(path, (ts, ts))


def test_no_data_directory_is_stale(tmp_path):
    run, reason = should_scrape("tullys", today=TODAY, data_root=tmp_path)
    assert run is True
    assert "tullys" in reason


def test_empty_directory_is_stale(tmp_path):
    (tmp_path / "tullys").mkdir()
    run, reason = should_scrape("tullys", today=TODAY, data_root=tmp_path)
    assert run is True
    assert "no parquet" in reason.lower()


def test_today_parquet_is_fresh(tmp_path):
    _write_parquet(tmp_path / "tullys" / PARQUET_NAME, mtime_date=TODAY)
    run, reason = should_scrape("tullys", today=TODAY, data_root=tmp_path)
    assert run is False
    assert "SKIP" in reason
    assert "fresh" in reason.lower()


def test_ten_day_old_parquet_is_fresh(tmp_path):
    file_date = TODAY - datetime.timedelta(days=10)
    _write_parquet(tmp_path / "tullys" / PARQUET_NAME, mtime_date=file_date)
    run, reason = should_scrape("tullys", today=TODAY, data_root=tmp_path)
    assert run is False
    assert "SKIP" in reason


def test_thirty_one_day_old_parquet_is_stale(tmp_path):
    file_date = TODAY - datetime.timedelta(days=31)
    _write_parquet(tmp_path / "tullys" / PARQUET_NAME, mtime_date=file_date)
    run, reason = should_scrape("tullys", today=TODAY, data_root=tmp_path)
    assert run is True
    assert "stale" in reason.lower()


def test_zero_row_parquet_is_stale(tmp_path):
    _write_parquet(tmp_path / "tullys" / PARQUET_NAME, rows=0, mtime_date=TODAY)
    run, reason = should_scrape("tullys", today=TODAY, data_root=tmp_path)
    assert run is True
    assert "0 rows" in reason


def test_custom_max_age_days(tmp_path):
    file_date = TODAY - datetime.timedelta(days=8)
    _write_parquet(tmp_path / "tullys" / PARQUET_NAME, mtime_date=file_date)
    run, reason = should_scrape(
        "tullys", max_age_days=7, today=TODAY, data_root=tmp_path
    )
    assert run is True
    assert "stale" in reason.lower()


def test_force_overrides_fresh(tmp_path):
    _write_parquet(tmp_path / "tullys" / PARQUET_NAME, mtime_date=TODAY)
    run, reason = should_scrape(
        "tullys", force=True, today=TODAY, data_root=tmp_path
    )
    assert run is True
    assert "FORCE" in reason
