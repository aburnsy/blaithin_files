"""Tests for cross-platform path handling in storage.py."""

from datetime import date

import polars as pl

from src.common.storage import export_data_locally


def test_export_data_locally_dated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    table = [{"source": "test_source", "product_name": "X", "price": 1.0}]
    export_data_locally(table=table, dated=True)
    expected = tmp_path / "data" / "test_source" / f"{date.today().isoformat()}.parquet"
    assert expected.exists()
    df = pl.read_parquet(expected)
    assert df.height == 1
    assert "input_date" in df.columns


def test_export_data_locally_undated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    table = [{"source": "rhs", "id": 1, "name": "Acer"}]
    export_data_locally(table=table, dated=False)
    expected = tmp_path / "data" / "rhs.parquet"
    assert expected.exists()


def test_export_data_locally_none_is_noop(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    export_data_locally(table=None)
    assert not (tmp_path / "data").exists()
    assert "no data" in capsys.readouterr().out


def test_export_data_locally_empty_is_noop(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    export_data_locally(table=[])
    assert not (tmp_path / "data").exists()
    assert "no data" in capsys.readouterr().out
