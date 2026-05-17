"""Read/write the human-auditable cache of LLM and manual match decisions.

The append-only ``data/llm_audit/resolutions_*.jsonl`` files are the source of
truth for what has been resolved. ``data/match_overrides.parquet`` is a
normalized snapshot rewritten only when a pipeline run finishes successfully,
plus any rows written by :func:`upsert_override` (manual entries).

Parquet writes are atomic: staged to ``<path>.tmp`` and ``os.replace``d into the
final location. A crash mid-write cannot truncate the live file.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import polars as pl

from src.matching.models import MatchOverride

OVERRIDES_PARQUET = Path(__file__).resolve().parents[2] / "data" / "match_overrides.parquet"

_EMPTY_SCHEMA = {
    "product_name_clean": pl.Utf8,
    "rhs_id": pl.Int64,
    "cultivar": pl.Utf8,
    "is_plant": pl.Boolean,
    "product_category": pl.Utf8,
    "source": pl.Utf8,
    "model": pl.Utf8,
    "created_at": pl.Datetime,
    "notes": pl.Utf8,
}


def _audit_dir() -> Path:
    """Directory holding the append-only LLM resolution audit logs."""
    return OVERRIDES_PARQUET.parent / "llm_audit"


def _load_jsonl_overrides() -> dict[str, MatchOverride]:
    """Read every ``resolutions_*.jsonl`` and return ``{name: latest override}``.

    Dedupe by ``product_name_clean`` keeping the entry with the latest
    ``created_at``. Files are processed in sorted-name order (filenames are
    timestamped, so this is also chronological).
    """
    audit = _audit_dir()
    if not audit.exists():
        return {}
    by_name: dict[str, MatchOverride] = {}
    for path in sorted(audit.glob("resolutions_*.jsonl")):
        try:
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ov = MatchOverride.model_validate(json.loads(line))
                    except Exception:
                        continue
                    existing = by_name.get(ov.product_name_clean)
                    if existing is None or ov.created_at >= existing.created_at:
                        by_name[ov.product_name_clean] = ov
        except OSError:
            continue
    return by_name


def load_overrides() -> list[MatchOverride]:
    """Merge the parquet snapshot with the append-only JSONL audit logs.

    The JSONL files are the canonical record of LLM resolutions; the parquet
    holds the last finalized snapshot plus any manual entries. On collision,
    manual rows always win; otherwise the entry with the later ``created_at``
    wins (so a JSONL-only resolution from a crashed run is recovered).
    """
    by_name: dict[str, MatchOverride] = {}

    if OVERRIDES_PARQUET.exists():
        df = pl.read_parquet(OVERRIDES_PARQUET)
        for row in df.iter_rows(named=True):
            ov = MatchOverride.model_validate(row)
            by_name[ov.product_name_clean] = ov

    for name, ov in _load_jsonl_overrides().items():
        existing = by_name.get(name)
        if existing is None:
            by_name[name] = ov
            continue
        if existing.source == "manual":
            continue
        if ov.source == "manual" or ov.created_at >= existing.created_at:
            by_name[name] = ov

    return list(by_name.values())


def save_overrides(overrides: list[MatchOverride]) -> None:
    """Atomically overwrite the overrides parquet with the given list.

    Writes to ``<OVERRIDES_PARQUET>.tmp`` first, then ``os.replace`` swaps it
    into place. If the process crashes mid-``write_parquet``, the live file is
    untouched; the dangling ``.tmp`` is harmless and overwritten on next save.
    """

    OVERRIDES_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    tmp = OVERRIDES_PARQUET.with_suffix(".parquet.tmp")

    if not overrides:
        pl.DataFrame(schema=_EMPTY_SCHEMA).write_parquet(tmp)
    else:
        df = pl.DataFrame([o.model_dump() for o in overrides])
        df.write_parquet(tmp)

    os.replace(tmp, OVERRIDES_PARQUET)


def upsert_override(override: MatchOverride) -> None:
    """Insert or replace an override (keyed on product_name_clean)."""

    existing = load_overrides()
    others = [o for o in existing if o.product_name_clean != override.product_name_clean]
    save_overrides(others + [override])


def new_audit_path(now: datetime) -> Path:
    """Return the JSONL audit-log path for a freshly started run."""
    audit = _audit_dir()
    audit.mkdir(parents=True, exist_ok=True)
    return audit / f"resolutions_{now.strftime('%Y%m%dT%H%M%SZ')}.jsonl"


def append_jsonl_overrides(path: Path, overrides: list[MatchOverride]) -> None:
    """Append one line per override to the audit log. Crash-safe per-line."""
    if not overrides:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for ov in overrides:
            fh.write(json.dumps(ov.model_dump(mode="json"), default=str) + "\n")
