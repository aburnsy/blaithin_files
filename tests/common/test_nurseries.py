"""Tests for nursery metadata loading."""

import pytest
from pydantic import ValidationError

from src.common.nurseries import NurseryConfig, load_nurseries, scraped_nursery_slugs


def test_load_nurseries_returns_dict_keyed_by_source():
    nurseries = load_nurseries()
    assert "tullys" in nurseries
    assert isinstance(nurseries["tullys"], NurseryConfig)


def test_tullys_config_shape():
    nurseries = load_nurseries()
    t = nurseries["tullys"]
    assert t.display_name == "Tully's Nurseries"
    assert t.currency == "EUR"
    # Tullys is the trade portal — lists ex-VAT prices; storage.py adds 23%.
    assert t.vat_included is False


def test_farmer_gracy_currency_is_gbp():
    nurseries = load_nurseries()
    fg = nurseries["farmer_gracy"]
    assert fg.currency == "GBP"


def test_nl_nurseries_flag_vat_status():
    nurseries = load_nurseries()
    # Bulbi.nl is a consumer storefront — listed prices already include VAT.
    assert nurseries["bulbi"].vat_included is True
    # GreenGardenFlowerBulbs is the B2B portal — lists ex-VAT prices.
    assert nurseries["greengardenflowerbulbs"].vat_included is False


def test_scraped_nursery_slugs_includes_github_actions_only():
    slugs = scraped_nursery_slugs()
    assert "tullys" in slugs  # runs_on: github-actions
    assert "hedgingie" in slugs  # runs_on: github-actions
    assert "david_austin" in slugs  # runs_on: github-actions
    # Magento-driven additions
    assert "bulbi" in slugs
    assert "greengardenflowerbulbs" in slugs
    assert "johnstown" in slugs


def test_greengardenflowerbulbs_records_per_box_delivery():
    nurseries = load_nurseries()
    g = nurseries["greengardenflowerbulbs"]
    # B2B wholesaler ships in fixed-size consignments; recorded so downstream
    # ship-cost calculations can pick the right unit fee.
    assert g.delivery_type == "per_box"
    assert g.delivery_per_box_eur == 21.50
    assert g.delivery_per_pallet_eur == 425
    # Min order applies — record it accurately.
    assert g.min_order_eur == 500


def test_per_box_fields_default_none_for_other_nurseries():
    nurseries = load_nurseries()
    # Hedges Direct is a flat-rate Shopify-style site, no per-box bookkeeping.
    assert nurseries["hedges_direct"].delivery_per_box_eur is None
    assert nurseries["hedges_direct"].delivery_per_pallet_eur is None


def test_invalid_currency_rejected():
    with pytest.raises(ValidationError):
        NurseryConfig(
            display_name="Test",
            base_url="https://example.com",
            currency="ZZZ",  # not a known ISO code in our enum
            vat_included=True,
            delivery_type="flat",
        )
