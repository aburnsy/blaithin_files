"""Shared pytest fixtures and global test isolation.

This module installs an **autouse fixture** that automatically redirects every
known module-level write-path into the test's ``tmp_path``. Even if an
individual test forgets to monkeypatch, it cannot pollute the real ``data/``,
``logs/``, or ``reports/`` directories.

The redirected paths are write-targets used by production code. Read-only
seeded data (``data/fx.parquet``, ``config/nurseries.yaml``) is deliberately
NOT redirected — tests that read it need the real file.

If a new module gains a write-side ``Path`` constant, add it to the
``_PRODUCTION_WRITE_PATHS`` list below to extend the safety net.
"""

from __future__ import annotations

import pytest

# Each entry is (dotted_attr, leaf_name_within_tmp_path).
# Order doesn't matter — they're independent.
_PRODUCTION_WRITE_PATHS: list[tuple[str, str]] = [
    ("src.matching.overrides.OVERRIDES_PARQUET", "match_overrides.parquet"),
    ("src.common.logging.LOG_DIR", "logs"),
    ("src.transforms.size_normalize.PRODUCTS_PARQUET", "products_matched.parquet"),
    ("src.common.report.REPORTS_DIR", "reports"),
]
# Note: the LLM-audit JSONL directory is derived from OVERRIDES_PARQUET.parent
# by src.matching.overrides._audit_dir, so it follows the monkeypatch above.


@pytest.fixture(autouse=True)
def _isolate_filesystem_writes(tmp_path, monkeypatch):
    """Redirect production write-paths to ``tmp_path`` for every test.

    Uses ``raising=False`` so the patch is a no-op when the target module
    hasn't been imported by the test (e.g. a scraper test that never touches
    the matching pipeline). Individual tests are still free to monkeypatch
    these paths to a more specific tmp location — the later patch wins.
    """
    for dotted, leaf in _PRODUCTION_WRITE_PATHS:
        monkeypatch.setattr(dotted, tmp_path / leaf, raising=False)
