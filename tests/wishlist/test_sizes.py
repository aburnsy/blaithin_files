"""Tests for cm and pot-code lookup tables."""

from src.wishlist.sizes import CM_TO_LITRES, POT_CODE_TO_CM


def test_cm_lookup_covers_7_to_50_inclusive():
    assert set(CM_TO_LITRES.keys()) == set(range(7, 51))


def test_cm_lookup_values_are_integers():
    assert all(isinstance(v, int) for v in CM_TO_LITRES.values())


def test_cm_lookup_monotonic_non_decreasing():
    sorted_keys = sorted(CM_TO_LITRES.keys())
    prev = -1
    for k in sorted_keys:
        assert CM_TO_LITRES[k] >= prev, f"{k}cm -> {CM_TO_LITRES[k]}L is less than previous"
        prev = CM_TO_LITRES[k]


def test_cm_lookup_known_anchors():
    # Anchors from spec §5.3
    assert CM_TO_LITRES[7] == 0
    assert CM_TO_LITRES[9] == 1
    assert CM_TO_LITRES[11] == 1
    assert CM_TO_LITRES[15] == 2
    assert CM_TO_LITRES[18] == 3
    assert CM_TO_LITRES[25] == 10
    assert CM_TO_LITRES[30] == 15
    assert CM_TO_LITRES[50] == 63


def test_pot_code_lookup_covers_known_codes():
    expected = {
        "P8.5", "P9", "P9.5",
        "P10", "P11", "P12", "P13", "P14", "P15",
        "P16", "P17", "P18", "P19", "P20",
        "P25", "P30",
    }
    assert set(POT_CODE_TO_CM.keys()) == expected


def test_pot_code_values_are_in_cm_table():
    # Every P-code must map to a cm value that exists in CM_TO_LITRES.
    for code, cm in POT_CODE_TO_CM.items():
        assert cm in CM_TO_LITRES, f"{code} -> {cm}cm not in CM_TO_LITRES"
