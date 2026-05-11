"""Wrapper around pygnparser returning our ``ParsedName`` model.

Backend: **pygnparser 0.0.5** — a Python shim that calls the GNA gnparser REST
API (parser.globalnames.org) under the hood. No Go binary required.

pygnparser exposes a ``Result`` object with methods like ``parsed()``,
``cardinality()``, ``genus()``, ``species()``. Cultivar names in single quotes
and cultivar groups like ``(Atropurpureum Group)`` are not part of the ICZN/ICBN
nomenclature that gnparser models, so they are left in the ``tail`` of the
parse result. We extract them via lightweight regex applied to the original
input string, then populate ``ParsedName`` accordingly.

Authorities (e.g. ``L.``, ``(L.) DC.``) are handled transparently: gnparser
strips them from the canonical name and we never see them.
"""

from __future__ import annotations

import re
from functools import lru_cache

import pygnparser

from src.matching.models import ParsedName


class ParseFailed(Exception):
    """gnparser could not parse the input as a binomial (genus + species) name."""


# Match a cultivar epithet in single typographic or straight quotes, e.g. 'Bloodgood'
_CULTIVAR_RE = re.compile(r"['‘’]([^'‘’]+)['‘’]")

# Match a cultivar group parenthetical, e.g. (Atropurpureum Group)
_GROUP_RE = re.compile(r"\(([^)]+\bGroup\b)\)")


@lru_cache(maxsize=10_000)
def parse(name: str) -> ParsedName:
    """Parse a botanical name string.

    Returns a :class:`~src.matching.models.ParsedName` with genus, species, and
    optional cultivar / cultivar_group fields populated.

    Raises :class:`ParseFailed` if the name cannot be resolved to at least a
    genus + species binomial (cardinality < 2 or gnparser fails to parse).

    LRU-cached to avoid hammering the gnparser network API on repeated lookups
    of the same product name (common across nursery sites and within a single
    matching run). ParsedName is frozen so it's safe to share.
    """
    result = pygnparser.gnparser(name)

    if not result.parsed():
        raise ParseFailed(f"Could not parse: {name!r}")

    if result.cardinality() < 2:
        raise ParseFailed(f"No genus+species in: {name!r}")

    genus = result.genus()
    species = result.species()

    # Extract cultivar from original name via regex — gnparser puts quoted
    # cultivar epithets in ``tail`` (un-parsed) but we fish them from the
    # raw input so we're resilient regardless of tail layout.
    cultivar: str | None = None
    m = _CULTIVAR_RE.search(name)
    if m:
        cultivar = m.group(1).strip()

    # Extract cultivar group parenthetical from original name.
    cultivar_group: str | None = None
    g = _GROUP_RE.search(name)
    if g:
        cultivar_group = g.group(1).strip()

    rank = result.parsed_result.get("rank") or None

    return ParsedName(
        genus=genus,
        species=species,
        cultivar=cultivar,
        cultivar_group=cultivar_group,
        rank=rank,
        raw=name,
    )
