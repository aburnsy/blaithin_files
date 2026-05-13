"""Pot-size lookup tables and constraint matching.

The single source of truth for diameter -> volume is ``CM_TO_LITRES``.
Pot codes (P9, P11, ...) funnel through ``POT_CODE_TO_CM`` first, so the
same physical pot always returns the same litre value regardless of how
the nursery labelled it.

The values are an approximation built from V ~= 0.5 * (d/10)^3, rounded
to integer litres. They differ from the historical stg_products.sql
mapping at some P-codes; internal consistency is favoured over matching
the older industry table. See spec §5.3 for the derivation.
"""

from __future__ import annotations


CM_TO_LITRES: dict[int, int] = {
    7: 0,  8: 0,  9: 1, 10: 1, 11: 1, 12: 1, 13: 1, 14: 2, 15: 2,
    16: 2, 17: 2, 18: 3, 19: 3, 20: 4, 21: 5, 22: 5, 23: 7, 24: 8,
    25: 10, 26: 11, 27: 12, 28: 13, 29: 14, 30: 15,
    31: 16, 32: 17, 33: 18, 34: 20, 35: 21, 36: 23, 37: 25, 38: 27,
    39: 30, 40: 32, 41: 35, 42: 37, 43: 40, 44: 43, 45: 46,
    46: 49, 47: 52, 48: 55, 49: 59, 50: 63,
}


POT_CODE_TO_CM: dict[str, int] = {
    "P8.5": 8, "P9": 9, "P9.5": 9,
    "P10": 10, "P11": 11, "P12": 12, "P13": 13, "P14": 14, "P15": 15,
    "P16": 16, "P17": 17, "P18": 18, "P19": 19, "P20": 20,
    "P25": 25, "P30": 30,
}
