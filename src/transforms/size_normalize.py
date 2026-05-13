"""Normalise the raw ``size`` string column into structured columns.

Reads ``data/products_matched.parquet`` (or any DataFrame with ``size`` +
``is_plant``) and adds two columns:

- ``pot_size_litres``: Float | None
- ``size_kind``: one of ``potted``, ``bare_root``, ``rootball``,
  ``unknown``, ``non_plant``

Designed to run after the matching pipeline. See spec §5 for the
parser semantics and the cm/pot-code tables.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import polars as pl

from src.wishlist.sizes import CM_TO_LITRES, POT_CODE_TO_CM

SizeKind = Literal["potted", "bare_root", "rootball", "unknown", "non_plant"]

PRODUCTS_PARQUET = Path(__file__).resolve().parents[2] / "data" / "products_matched.parquet"


_RE_BARE_ROOT = re.compile(r"bare\s*root", re.IGNORECASE)
_RE_ROOTBALL = re.compile(r"rootball", re.IGNORECASE)
_RE_LITRE_RANGE = re.compile(r"(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*(?:L|Lit)", re.IGNORECASE)
_RE_LITRE_SINGLE = re.compile(r"(\d+\.?\d*)\s*(?:L|Lit)", re.IGNORECASE)
_RE_POT_CODE = re.compile(r"\bP(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_RE_CM = re.compile(r"(\d+(?:\.\d+)?)\s*cm", re.IGNORECASE)


def parse_size(size_str: str | None, *, is_plant: bool) -> tuple[SizeKind, float | None]:
    """Parse a single ``size`` cell into ``(size_kind, pot_size_litres)``.

    Always returns ("non_plant", None) when ``is_plant`` is False.
    Returns ("unknown", None) for empty / None / unparsable strings.
    """

    if not is_plant:
        return "non_plant", None
    if size_str is None or not size_str.strip():
        return "unknown", None

    s = size_str.strip()

    # Order matters: bare-root / rootball strings can contain digits we
    # don't want to interpret as litres.
    if _RE_BARE_ROOT.search(s):
        return "bare_root", None
    if _RE_ROOTBALL.search(s):
        return "rootball", None

    if m := _RE_LITRE_RANGE.search(s):
        return "potted", float(m.group(1))   # lower bound
    if m := _RE_LITRE_SINGLE.search(s):
        return "potted", float(m.group(1))
    if m := _RE_POT_CODE.search(s):
        code = "P" + m.group(1)
        cm = POT_CODE_TO_CM.get(code)
        if cm is None:
            return "unknown", None
        return "potted", float(CM_TO_LITRES[cm])
    if m := _RE_CM.search(s):
        cm_rounded = round(float(m.group(1)))
        if cm_rounded not in CM_TO_LITRES:
            return "unknown", None
        return "potted", float(CM_TO_LITRES[cm_rounded])

    return "unknown", None


def add_size_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Return a copy of ``df`` with ``pot_size_litres`` and ``size_kind`` added.

    Expects columns ``size`` (String, nullable) and ``is_plant`` (Boolean).
    """

    pairs = [
        parse_size(s, is_plant=p)
        for s, p in zip(df["size"].to_list(), df["is_plant"].to_list(), strict=True)
    ]
    kinds = [k for k, _ in pairs]
    litres = [v for _, v in pairs]
    return df.with_columns([
        pl.Series("size_kind", kinds, dtype=pl.String),
        pl.Series("pot_size_litres", litres, dtype=pl.Float64),
    ])


def run() -> None:
    """Read products_matched.parquet, add the size columns, write back."""

    df = pl.read_parquet(PRODUCTS_PARQUET)
    out = add_size_columns(df)
    out.write_parquet(PRODUCTS_PARQUET)
    print(f"Wrote {len(out)} rows -> {PRODUCTS_PARQUET}")


if __name__ == "__main__":
    run()
