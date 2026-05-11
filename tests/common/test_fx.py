"""Tests for FX rate conversion."""

from datetime import date
from decimal import Decimal

import pytest

from src.common.fx import to_eur, FxRateMissing


def test_to_eur_passthrough_for_eur():
    assert to_eur(10.0, "EUR", date(2026, 5, 11)) == 10.0


def test_to_eur_converts_gbp():
    # Use a real recent date that's in the seeded fx.parquet
    result = to_eur(10.0, "GBP", date(2026, 5, 1))
    assert 10.0 < result < 15.0  # GBP > EUR historically; sanity bound


def test_to_eur_missing_rate_raises():
    with pytest.raises(FxRateMissing):
        to_eur(10.0, "GBP", date(1900, 1, 1))


def test_to_eur_unknown_currency_raises():
    with pytest.raises(ValueError, match="Unknown currency"):
        to_eur(10.0, "ZZZ", date(2026, 5, 11))
