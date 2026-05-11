"""Tests for nursery metadata loading."""

import pytest
from pydantic import ValidationError

from src.common.nurseries import NurseryConfig, load_nurseries


def test_load_nurseries_returns_dict_keyed_by_source():
    nurseries = load_nurseries()
    assert "tullys" in nurseries
    assert isinstance(nurseries["tullys"], NurseryConfig)


def test_tullys_config_shape():
    nurseries = load_nurseries()
    t = nurseries["tullys"]
    assert t.display_name == "Tully's Nurseries"
    assert t.currency == "EUR"
    assert t.vat_included is True


def test_farmer_gracy_currency_is_gbp():
    nurseries = load_nurseries()
    fg = nurseries["farmer_gracy"]
    assert fg.currency == "GBP"


def test_nl_nurseries_flag_vat_status():
    nurseries = load_nurseries()
    bulbi = nurseries["bulbi"]
    assert bulbi.vat_included is False  # IE buyers may face customs VAT


def test_invalid_currency_rejected():
    with pytest.raises(ValidationError):
        NurseryConfig(
            display_name="Test",
            base_url="https://example.com",
            currency="ZZZ",  # not a known ISO code in our enum
            vat_included=True,
            delivery_type="flat",
        )
