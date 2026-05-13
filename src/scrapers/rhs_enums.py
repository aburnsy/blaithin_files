"""Decode tables for RHS plant detail API integer enums.

The RHS Angular frontend (main.bundle.js) carries these maps as TS enums; we
mirror them here so the scraper can emit human-readable strings. If the API
ever changes a value, the raw JSON kept in the staging sqlite lets us re-decode
without re-fetching.
"""

from __future__ import annotations

# Used by rhs_urls.py to map the integer plantType -> human label when building
# the search request, and by the detail scraper to decode plantType lists.
PLANT_TYPE: dict[int, str] = {
    1: "Herbaceous Perennial",
    2: "Climber Wall Shrub",
    3: "Bedding",
    4: "Bulbs",
    5: "Ferns",
    6: "Shrubs",
    7: "Annual Biennial",
    8: "Alpine Rockery",
    9: "Roses",
    10: "Grasses",
    11: "Conservatory Greenhouse",
    12: "Fruit Edible",
    13: "Trees",
    14: "Houseplants",
    15: "Cactus Succulent",
    16: "Aquatic",
    17: "Bamboos",
    18: "Bogs",
    19: "Conifers",
    20: "Herbs",
    21: "Palms",
}

SUNLIGHT: dict[int, str] = {
    0: "No preference",
    1: "Full sun",
    2: "Partial shade",
    3: "Full shade",
}

SOIL_TYPE: dict[int, str] = {
    0: "No preference",
    1: "Loam",
    2: "Chalk",
    3: "Sand",
    4: "Clay",
}

ASPECT: dict[int, str] = {
    0: "No preference",
    1: "East-facing",
    2: "North-facing",
    3: "South-facing",
    4: "West-facing",
}

MOISTURE: dict[int, str] = {
    0: "No preference",
    1: "Well-drained",
    2: "Poorly drained",
    3: "Moist but well-drained",
}

PH: dict[int, str] = {
    0: "No preference",
    1: "Acid",
    2: "Alkaline",
    3: "Neutral",
}

EXPOSURE: dict[int, str] = {
    0: "No preference",
    1: "Sheltered",
    2: "Exposed",
}

FOLIAGE: dict[int, str] = {
    0: "No preference",
    1: "Deciduous",
    2: "Evergreen",
    3: "Semi evergreen",
}

HABIT: dict[int, str] = {
    0: "No preference",
    1: "Bushy",
    2: "Climbing",
    3: "Clump-forming",
    4: "Columnar/upright",
    5: "Floating",
    6: "Mat-forming",
    7: "Pendulous/weeping",
    8: "Spreading branched",
    9: "Submerged",
    10: "Suckering",
    11: "Trailing",
    12: "Tufted",
}

# The Angular bundle has a collision: H4 and H5 both map to 6. We label the
# ambiguous slot accordingly rather than picking one silently.
HARDINESS: dict[int, str] = {
    0: "Unknown",
    1: "H1A",
    2: "H1B",
    3: "H1C",
    4: "H2",
    5: "H3",
    6: "H4/H5",
    7: "H6",
    8: "H7",
}


def decode_list(values: list[int] | None, table: dict[int, str]) -> list[str]:
    """Decode a list of int enums to labels, dropping unknown ints rather than raising."""
    if not values:
        return []
    out: list[str] = []
    for v in values:
        label = table.get(v)
        if label is not None:
            out.append(label)
    return out


def decode_scalar(value: int | None, table: dict[int, str]) -> str | None:
    """Decode a single int enum to a label, returning None for missing/unknown."""
    if value is None:
        return None
    return table.get(value)
