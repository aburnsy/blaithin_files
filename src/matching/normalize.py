"""Strip nursery cruft from product names so the parser sees clean botanical input."""

from __future__ import annotations

import re

# Order matters: more-specific patterns before more-general ones.
_PATTERNS = [
    re.compile(r"\b\d+\s*(?:cm|mm|m)\b", re.IGNORECASE),                # heights/widths in cm/mm/m
    re.compile(r"\b\d+\s*(?:l|ltr|litre|liter)\b", re.IGNORECASE),      # pot volumes
    re.compile(r"\bP\d+\b", re.IGNORECASE),                             # pot codes (P9, P15)
    re.compile(r"\b\d+\s*(?:bulbs?|seeds?|plugs?|packs?)\b", re.IGNORECASE),
    re.compile(r"\bpack\s+of\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bpot\b", re.IGNORECASE),                              # trailing "pot" after size stripped
    re.compile(r"\(\s*[A-Z][a-z]+(?:\s+[A-Za-z]+)+\s*\)"),             # (Common Name) trailing parens
    re.compile(r"\s+"),                                                  # collapse whitespace runs
]


def clean_product_name(raw: str) -> str:
    """Return a botanical-name-only version of `raw`.

    Strips pot codes, sizes, quantity packs, and common-name parentheticals.
    Preserves cultivar quotes (`'Bloodgood'`) and binomial structure.
    """

    s = raw
    for pattern in _PATTERNS[:-1]:
        s = pattern.sub(" ", s)
    # final whitespace collapse
    s = _PATTERNS[-1].sub(" ", s).strip()
    return s
