"""Botanical name parser with two backends.

Default backend: **local regex** — no network, fast, handles the 95% case
(binomial + optional cultivar in single quotes + optional Group parenthetical).
Sufficient for nursery product matching.

Optional backend: **pygnparser** — calls parser.globalnames.org for
authority-stripping and edge cases (rank notation, hybrid notation). Used
only when the local parser fails AND ``BLAITHIN_USE_GNPARSER=1`` is set.

The reason for the local-first default: parser.globalnames.org is unreliable
for bulk use (per-name HTTP round-trip with frequent timeouts on Windows). A
local regex is good enough for nursery data and never fails for network reasons.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache

from src.matching.models import ParsedName


class ParseFailed(Exception):
    """Could not parse the input as a binomial (genus + species) name."""


# Match a cultivar epithet in single typographic or straight quotes, e.g. 'Bloodgood'
_CULTIVAR_RE = re.compile(r"['‘’]([^'‘’]+)['‘’]")

# Match a cultivar group parenthetical, e.g. (Atropurpureum Group)
_GROUP_RE = re.compile(r"\(([^)]+\bGroup\b)\)")

# A genus token: capitalised, alpha (no digits)
_GENUS_RE = re.compile(r"\b[A-Z][a-z]+\b")

# A species epithet token: lowercase, alpha (allow hyphens for things like coeli-rosa)
_SPECIES_RE = re.compile(r"\b[a-z]+(?:-[a-z]+)?\b")

# Authority markers and common cruft to skip when looking for species
_SKIP_TOKENS = {"the", "and", "or", "of", "for", "in", "with", "from"}


def _local_parse(name: str) -> ParsedName:
    """Pure-Python regex parser.

    Strategy: find the first capitalised word (genus), then the next lowercase
    word that isn't a stopword (species). Cultivar from single quotes; group
    from ``(... Group)`` parenthetical.

    Raises ParseFailed if either genus or species can't be found.
    """
    # Strip the cultivar parenthetical and quotes from the working string so they
    # don't interfere with genus/species detection
    working = _CULTIVAR_RE.sub(" ", name)
    working = _GROUP_RE.sub(" ", working)

    genus_m = _GENUS_RE.search(working)
    if not genus_m:
        raise ParseFailed(f"No genus in: {name!r}")
    genus = genus_m.group(0)

    # Look for species AFTER the genus position; skip stopwords
    after_genus = working[genus_m.end():]
    species = None
    for token in _SPECIES_RE.findall(after_genus):
        if token.lower() not in _SKIP_TOKENS:
            species = token
            break
    if species is None:
        raise ParseFailed(f"No species after {genus!r} in: {name!r}")

    cultivar: str | None = None
    m = _CULTIVAR_RE.search(name)
    if m:
        cultivar = m.group(1).strip()

    cultivar_group: str | None = None
    g = _GROUP_RE.search(name)
    if g:
        cultivar_group = g.group(1).strip()

    return ParsedName(
        genus=genus,
        species=species,
        cultivar=cultivar,
        cultivar_group=cultivar_group,
        rank=None,
        raw=name,
    )


def _gnparser_parse(name: str) -> ParsedName:
    """Network-backed parser via pygnparser. Slow + flaky; opt-in only."""
    import pygnparser  # imported lazily so the dep is optional in practice

    result = pygnparser.gnparser(name)

    if not result.parsed():
        raise ParseFailed(f"Could not parse: {name!r}")
    if result.cardinality() < 2:
        raise ParseFailed(f"No genus+species in: {name!r}")

    cultivar: str | None = None
    m = _CULTIVAR_RE.search(name)
    if m:
        cultivar = m.group(1).strip()

    cultivar_group: str | None = None
    g = _GROUP_RE.search(name)
    if g:
        cultivar_group = g.group(1).strip()

    return ParsedName(
        genus=result.genus(),
        species=result.species(),
        cultivar=cultivar,
        cultivar_group=cultivar_group,
        rank=result.parsed_result.get("rank") or None,
        raw=name,
    )


@lru_cache(maxsize=10_000)
def parse(name: str) -> ParsedName:
    """Parse a botanical name string.

    Returns :class:`~src.matching.models.ParsedName`. Raises
    :class:`ParseFailed` if neither backend can resolve it.

    Default: local regex parser (fast, offline, handles the 95% case).
    Set ``BLAITHIN_USE_GNPARSER=1`` to try the network-backed parser FIRST
    (more accurate on edge cases like authority strings and rank notation),
    falling back to local on any failure.

    LRU-cached either way.
    """
    if os.environ.get("BLAITHIN_USE_GNPARSER") == "1":
        try:
            return _gnparser_parse(name)
        except Exception:  # network timeout, parse failure, anything
            pass  # fall through to local

    return _local_parse(name)
