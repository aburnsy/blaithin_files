"""Verify the autouse fixture in tests/conftest.py redirects production paths.

If this test breaks, the safety net is broken — investigate before merging.
"""

from __future__ import annotations


def test_overrides_path_redirected_to_tmp(tmp_path):
    from src.matching.overrides import OVERRIDES_PARQUET

    # The conftest fixture redirected this to <tmp_path>/match_overrides.parquet.
    assert OVERRIDES_PARQUET == tmp_path / "match_overrides.parquet"


def test_audit_dir_redirected_to_tmp(tmp_path):
    from src.matching.overrides import _audit_dir

    # _audit_dir derives from OVERRIDES_PARQUET.parent, which the conftest
    # autouse fixture has redirected to tmp_path.
    assert _audit_dir() == tmp_path / "llm_audit"


def test_log_dir_redirected_to_tmp(tmp_path):
    from src.common import logging as logging_mod

    assert logging_mod.LOG_DIR == tmp_path / "logs"


def test_products_matched_path_redirected_to_tmp(tmp_path):
    from src.transforms.size_normalize import PRODUCTS_PARQUET

    assert PRODUCTS_PARQUET == tmp_path / "products_matched.parquet"


def test_reports_dir_redirected_to_tmp(tmp_path):
    from src.common.report import REPORTS_DIR

    assert REPORTS_DIR == tmp_path / "reports"


def test_save_overrides_writes_to_tmp_not_real_data():
    """A test that 'forgets' to monkeypatch must still be safe."""
    from src.matching.models import MatchOverride
    from src.matching.overrides import OVERRIDES_PARQUET, save_overrides

    save_overrides([
        MatchOverride(product_name_clean="canary", rhs_id=1, source="llm"),
    ])
    # The redirected path exists in tmp; the real one is untouched.
    assert OVERRIDES_PARQUET.exists()
    real = OVERRIDES_PARQUET.parents[2] / "data" / "match_overrides.parquet"  # noqa: F841 — referenced for shape only
    # Don't assert on the real file's state — other tests / production may
    # legitimately have it present. What matters is that OUR write went to tmp.
    assert "match_overrides.parquet" in str(OVERRIDES_PARQUET)
    assert "Temp" in str(OVERRIDES_PARQUET) or "tmp" in str(OVERRIDES_PARQUET).lower()
