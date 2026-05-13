"""Sqlite staging + resume + finalise behaviour, no network."""

from __future__ import annotations

import threading

import polars as pl
import pytest

from src.scrapers import rhs


@pytest.fixture
def tmp_dirs(tmp_path, monkeypatch):
    data_dir = tmp_path / "data" / "rhs"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr(rhs, "DATA_DIR", data_dir)
    monkeypatch.setattr(rhs, "STAGING_DB", data_dir / "_staging.sqlite")
    monkeypatch.setattr(rhs, "FINAL_PARQUET", data_dir / "data.parquet")
    monkeypatch.setattr(rhs, "FAILED_IDS_TXT", data_dir / "failed_ids.txt")
    return data_dir


def _payload(id_: int) -> dict:
    return {
        "id": id_,
        "botanicalName": f"<em>Genus{id_}</em> species{id_}",
        "botanicalNameUnFormatted": f"Genus{id_} species{id_}",
        "commonName": f"Common {id_}",
        "commonNames": [f"Common {id_}"],
        "family": "Familyaceae",
        "genus": f"Genus{id_}",
        "synonyms": [],
        "isAgm": False,
        "isPlantsForPollinators": True,
        "height": "1-2 metres",
        "spread": "1-2 metres",
        "sunlight": [1],
        "soilType": [2],
        "moisture": [3],
        "ph": [1, 2],
        "aspect": [1],
        "exposure": [1],
        "plantType": [6],
        "foliage": [1],
        "habit": [1],
        "hardinessLevel": 7,
        "entityDescription": f"Description {id_}",
    }


def test_seen_ids_returns_inserted_rows(tmp_dirs):
    conn = rhs._open_db()
    lock = threading.Lock()
    for id_ in (10, 20, 30):
        rhs._record_success(conn, lock, id_, _payload(id_), rhs.parse_detail(_payload(id_)))

    assert rhs._seen_ids(conn) == {10, 20, 30}
    conn.close()


def test_record_failure_increments_attempts(tmp_dirs):
    conn = rhs._open_db()
    lock = threading.Lock()
    rhs._record_failure(conn, lock, 99, "404")
    rhs._record_failure(conn, lock, 99, "timeout")
    rows = list(conn.execute("SELECT id, reason, attempts FROM failed_ids"))
    assert rows == [(99, "timeout", 2)]
    conn.close()


def test_success_clears_prior_failure(tmp_dirs):
    conn = rhs._open_db()
    lock = threading.Lock()
    rhs._record_failure(conn, lock, 42, "500")
    assert rhs._failed_id_set(conn) == {42}

    rhs._record_success(conn, lock, 42, _payload(42), rhs.parse_detail(_payload(42)))
    assert rhs._failed_id_set(conn) == set()
    assert rhs._seen_ids(conn) == {42}
    conn.close()


def test_final_parquet_round_trip(tmp_dirs):
    conn = rhs._open_db()
    lock = threading.Lock()
    for id_ in (1, 2):
        rhs._record_success(conn, lock, id_, _payload(id_), rhs.parse_detail(_payload(id_)))

    n = rhs._write_final_parquet(conn)
    assert n == 2
    df = pl.read_parquet(rhs.FINAL_PARQUET)
    assert set(df["rhs_id"].to_list()) == {1, 2}
    # Schema columns we promised in the design doc
    for col in (
        "rhs_id", "plant_url", "botanical_name", "genus", "species", "family",
        "common_name", "common_names", "synonyms", "plant_type", "description",
        "is_rhs_award_winner", "is_pollinator_plant", "height", "spread",
        "soils", "moisture", "ph", "sun_exposure", "aspect", "exposure",
        "hardiness", "foliage", "habit", "source",
    ):
        assert col in df.columns, f"missing column {col!r}"
    conn.close()


def test_dump_failed_ids_writes_file(tmp_dirs):
    conn = rhs._open_db()
    lock = threading.Lock()
    rhs._record_failure(conn, lock, 7, "404")
    rhs._record_failure(conn, lock, 8, "Timeout")
    n = rhs._dump_failed_ids(conn)
    assert n == 2
    text = rhs.FAILED_IDS_TXT.read_text(encoding="utf-8")
    assert "7\t404" in text
    assert "8\tTimeout" in text
    conn.close()


def test_dump_failed_ids_removes_stale_sidecar_when_empty(tmp_dirs):
    rhs.FAILED_IDS_TXT.write_text("stale\n", encoding="utf-8")
    conn = rhs._open_db()
    assert rhs._dump_failed_ids(conn) == 0
    assert not rhs.FAILED_IDS_TXT.is_file()
    conn.close()


def test_remove_legacy_per_plant_files(tmp_dirs):
    # Drop a few legacy per-plant parquet files into the dir
    (tmp_dirs / "12345.parquet").write_bytes(b"not a real parquet")
    (tmp_dirs / "67890.parquet").write_bytes(b"")
    # And the canonical name we DO want to keep if it already exists
    (tmp_dirs / "data.parquet").write_bytes(b"keep me")

    removed = rhs._remove_legacy_per_plant_files(tmp_dirs)
    assert removed == 2
    assert not (tmp_dirs / "12345.parquet").exists()
    assert not (tmp_dirs / "67890.parquet").exists()
    assert (tmp_dirs / "data.parquet").exists()
