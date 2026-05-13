"""Tests for cross-platform path handling in storage.py."""

import polars as pl
import pytest

from src.common.storage import export_data_locally, _apply_vat_if_needed


def test_export_data_locally_dated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    table = [{"source": "test_source", "product_name": "X", "price": 1.0}]
    export_data_locally(table=table, dated=True)
    expected = tmp_path / "data" / "test_source" / "data.parquet"
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


def test_apply_vat_raises_on_config_load_failure(monkeypatch):
    """If nurseries.yaml fails to validate, we must not silently write
    ex-VAT data for an ex-VAT source. Repro of the bug that hit Tullys
    when a long-running scraper saw a config field its in-memory pydantic
    enum didn't know about.
    """
    import src.common.storage as storage

    def _boom():
        raise ValueError("simulated config validation error")

    monkeypatch.setattr(storage, "load_nurseries", _boom)
    df = pl.DataFrame({"source": ["tullys"], "price": [100.0]})
    with pytest.raises(RuntimeError, match="Cannot load nurseries config"):
        _apply_vat_if_needed(df, "tullys")
