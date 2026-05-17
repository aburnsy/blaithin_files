"""Strip nursery cruft from product names so the parser sees clean botanical input.

The goal is a canonical ``product_name_clean`` that is identical across nurseries
for the same plant — so the override cache (keyed on this string) collapses
"OLEA europaea Pompon 200/250" and "Olea Europaea / Olive trees girth" and
"olea europaea (Olive)" into a single entry.

Cleaning steps, applied in order outside any single-quoted cultivar segment:

1. Unicode NFKC + replace U+FFFD with space.
2. Strip pot codes, volumes, heights, quantity packs.
3. Strip parentheticals — EXCEPT ``(... Group)`` which the gnparser needs.
4. Strip topiary/form descriptors and bare numeric size ranges.
5. Strip everything after the first ``/`` (a common-name slash suffix like
   "/ Olive Tree girth").
6. Strip a small set of common-name suffix words ("Tree", "Mature", …).
7. Strip ``x \\d+`` quantity multipliers.
8. Case-fold: lowercase everything outside quotes, then capitalise the first
   alphabetic character so the gnparser regex (which expects a Title-Case
   genus) still works.
"""

from __future__ import annotations

import re
import unicodedata

# Patterns applied in order, OUTSIDE quoted cultivar segments.
# Multi-word descriptors must come before their single-word variants so the
# longer match wins (e.g. "Half Standard" before "Standard").
_PATTERNS = [
    re.compile(r"\b\d+\s*(?:cm|mm|m)\b", re.IGNORECASE),                # heights/widths
    re.compile(r"\b\d+\s*(?:l|ltr|litre|liter)\b", re.IGNORECASE),      # pot volumes
    re.compile(r"\bP\d+\b", re.IGNORECASE),                             # pot codes (P9, P15)
    re.compile(r"\b\d+\s*(?:bulbs?|seeds?|plugs?|packs?)\b", re.IGNORECASE),
    re.compile(r"\bpack\s+of\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bpot\b", re.IGNORECASE),
    # Drop any parenthetical that does NOT contain "Group" (gnparser uses
    # "(... Group)" for cultivar groups; preserve those).
    re.compile(r"\(\s*(?![^)]*\bGroup\b)[^)]*\)"),
    # Multi-word topiary/form descriptors.
    re.compile(
        r"\b(?:"
        r"Half\s+Standard|"
        r"[13]/[24]\s+Standard(?:\s+Stem)?|"
        r"Pompon\s+Ball|"
        r"Pom\s*Pom|"
        r"Old\s+Skin|Young\s+Skin|Old\s+Bark|Young\s+Bark|Old\s+Logs|"
        r"Pleached(?:\s+Panel)?|"
        r"Forma\s+[A-Z][a-z]+|"
        r"Art\.\s*\d+(?:\s+Old\s+Logs)?|"
        r"Multi[-\s]?Stem|"
        r"Bare\s*Root(?:ed)?"
        r")\b",
        re.IGNORECASE,
    ),
    # Single-word topiary/form/common-name descriptors.
    re.compile(
        r"\b(?:Standard|Stem|Crown|Bush|Ball|Bonsai|Pompon|Branched|"
        r"Bowl|Extra|Tarrina|Specimen|Topiary|Espalier|Cordon|"
        r"Tree|Mature|Girth|Hedge|Hedging|Container|Cont|"
        r"Rootball|Mini|Double|Single|Plant|Plants)\b",
        re.IGNORECASE,
    ),
    # "x N" quantity multipliers must run BEFORE the bare-digit pattern below,
    # otherwise the digit is consumed first and a stray "x" leaks through.
    # The botanical hybrid marker "x" + lowercase word (e.g. "Pinus x
    # leucodermis") is left alone — this pattern requires digits after "x".
    re.compile(r"\bx\s+\d+\b", re.IGNORECASE),
    # Numeric size ranges and bare callipers/heights, e.g. "120/150", "40-",
    # "10/12", "40+", trailing "100".
    re.compile(r"\b\d+\s*[-+/](?:\s*\d+)?(?!\d)"),
    re.compile(r"\b\d+\+?\b"),
    # Strip everything from the first remaining "/" to end (after numeric
    # ranges have been consumed above, a leftover slash is a common-name
    # suffix like "/ Olive Tree girth").
    re.compile(r"\s*/.*$"),
    # Empty leftover parens like "( )" after inner stripping.
    re.compile(r"\(\s*\)"),
]

_WHITESPACE = re.compile(r"\s+")
_LEADING_TRAILING_PUNCT = re.compile(r"^[\s.,;:&\-/]+|[\s.,;:&\-/]+$")
_FFFD = "�"


def _strip_outside_quotes(raw: str) -> str:
    """Apply every pattern in ``_PATTERNS`` only to non-quoted segments.

    Splits the string on single-quote runs; even-indexed parts (outside quotes)
    are scrubbed, odd-indexed parts (the cultivar literals) are passed through
    unchanged.
    """
    parts = raw.split("'")
    for i, seg in enumerate(parts):
        if i % 2 == 1:
            continue
        for pattern in _PATTERNS:
            seg = pattern.sub(" ", seg)
        parts[i] = seg
    return "'".join(parts)


def _case_fold(s: str) -> str:
    """Canonicalise case for dedup: lowercase outside quotes, then capitalise
    the first alphabetic char so the gnparser regex matches a Title-Case genus.

    Examples:
        "OLEA europaea"  -> "Olea europaea"
        "Olea Europaea"  -> "Olea europaea"
        "olea europaea"  -> "Olea europaea"
        "Olea 'Bloodgood'" -> "Olea 'Bloodgood'"  (cultivar preserved verbatim)
    """
    parts = s.split("'")
    for i, seg in enumerate(parts):
        if i % 2 == 1:
            continue
        parts[i] = seg.lower()
    s = "'".join(parts)

    # Capitalise the first alphabetic char (it's the genus position).
    for idx, ch in enumerate(s):
        if ch.isalpha():
            s = s[:idx] + ch.upper() + s[idx + 1:]
            break
    return s


def clean_product_name(raw: str) -> str:
    """Return the canonical cleaned form of ``raw``.

    Idempotent: ``clean_product_name(clean_product_name(x)) == clean_product_name(x)``.
    """
    s = unicodedata.normalize("NFKC", raw).replace(_FFFD, " ")
    s = _strip_outside_quotes(s)
    s = _WHITESPACE.sub(" ", s)
    s = _LEADING_TRAILING_PUNCT.sub("", s).strip()
    s = _case_fold(s)
    return s
