"""Tests for the edit_overrides CLI."""

import subprocess
import sys

from src.matching.models import MatchOverride
from src.matching.overrides import save_overrides


def test_list_command_prints_overrides(tmp_path, monkeypatch):
    p = tmp_path / "match_overrides.parquet"
    monkeypatch.setattr("src.matching.overrides.OVERRIDES_PARQUET", p)
    save_overrides([
        MatchOverride(product_name_clean="acer palmatum bloodgood", rhs_id=42, source="llm"),
    ])
    result = subprocess.run(
        [sys.executable, "scripts/edit_overrides.py", "list"],
        capture_output=True, text=True,
        env={"OVERRIDES_PARQUET": str(p), **dict(__import__("os").environ)},
    )
    assert result.returncode == 0
    assert "acer palmatum bloodgood" in result.stdout
    assert "42" in result.stdout
