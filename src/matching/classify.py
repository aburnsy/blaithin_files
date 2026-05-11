"""Deterministic non-plant prefilter.

Rules:
  - Strong product-category keyword in the name → non-plant, category = matched.
  - parsed is not None and indicators of bulb/seed → plant, but category = bulb/seed.
  - parsed is not None otherwise → plant, category = plant.
  - Else → non-plant, category = other (LLM may refine in Phase D).
"""

from __future__ import annotations

import re
from typing import Optional

from src.matching.models import ParsedName, ProductCategory

_NON_PLANT_PATTERNS: list[tuple[re.Pattern[str], ProductCategory]] = [
    (re.compile(r"\b(?:compost|peat|loam|topsoil|gravel|grit|mulch)\b", re.I), "compost"),
    (re.compile(r"\b(?:fertili[sz]er|feed|tonic|spray)\b", re.I), "fertiliser"),
    (re.compile(r"\b(?:secateurs?|spade|fork|rake|shears|trowel|hoe|loppers|wheelbarrow)\b", re.I), "tool"),
    (re.compile(r"\b(?:pot|planter|trough|tray|module|cell)\b", re.I), "pot"),
    (re.compile(r"\b(?:net|fleece|cloche|cane|stake|tie|tag|label)\b", re.I), "accessory"),
]

_BULB_INDICATORS = re.compile(r"\b(?:bulb|bulbs|tuber|tubers|corm|corms|rhizome)\b", re.I)
_SEED_INDICATORS = re.compile(r"\b(?:seed|seeds|seed packet|sachet)\b", re.I)


def classify_product(
    raw: str, parsed: Optional[ParsedName]
) -> tuple[bool, ProductCategory]:
    """Return (is_plant, product_category) for a product."""

    # Step 1: explicit non-plant keywords win
    for pattern, category in _NON_PLANT_PATTERNS:
        if pattern.search(raw):
            return False, category

    # Step 2: parsed plant + bulb/seed indicator → bulb/seed sub-category
    if parsed is not None:
        if _BULB_INDICATORS.search(raw):
            return True, "bulb"
        if _SEED_INDICATORS.search(raw):
            return True, "seed"
        return True, "plant"

    # Step 3: nothing parsed and no keyword → other
    return False, "other"
