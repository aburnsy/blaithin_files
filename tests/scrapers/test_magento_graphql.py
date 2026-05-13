"""Tests for the MagentoGraphQLScraper base class.

Synthetic GraphQL response fragments — no live calls. Covers:
  - simple product row build
  - configurable product variant expansion (one row per variant)
  - graceful skip when price_range is missing
  - the include_stock_status toggle removes stock_status from the query
"""

from __future__ import annotations

from src.scrapers.magento_graphql import (
    MagentoGraphQLScraper,
    _build_list_query,
)


class _Probe(MagentoGraphQLScraper):
    source = "probe"
    base_url = "https://example.test"
    currency = "EUR"


def _simple_item():
    return {
        "__typename": "SimpleProduct",
        "sku": "ABC-1",
        "name": "Tulip Bulb Mix",
        "url_key": "tulip-bulb-mix",
        "stock_status": "IN_STOCK",
        "categories": [{"name": "Bulbs"}, {"name": "Spring"}],
        "image": {"url": "https://example.test/img/abc1.jpg"},
        "short_description": {"html": "<p>Mixed colours.</p>"},
        "price_range": {"minimum_price": {"final_price": {"value": 7.95, "currency": "EUR"}}},
    }


def _configurable_item():
    base = _simple_item()
    base["__typename"] = "ConfigurableProduct"
    base["sku"] = "ABC-CFG"
    base["variants"] = [
        {
            "product": {
                "sku": "ABC-CFG-50",
                "name": "Tulip Bulb Mix 50",
                "stock_status": "IN_STOCK",
                "price_range": {"minimum_price": {"final_price": {"value": 14.95, "currency": "EUR"}}},
            },
            "attributes": [{"code": "pack_size", "label": "50 bulbs"}],
        },
        {
            "product": {
                "sku": "ABC-CFG-100",
                "name": "Tulip Bulb Mix 100",
                "stock_status": "OUT_OF_STOCK",
                "price_range": {"minimum_price": {"final_price": {"value": 24.95, "currency": "EUR"}}},
            },
            "attributes": [{"code": "pack_size", "label": "100 bulbs"}],
        },
    ]
    return base


def test_simple_product_emits_one_row():
    rows = _Probe().parse_records(_simple_item(), "https://example.test/graphql")
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "probe"
    assert r["currency"] == "EUR"
    assert r["price_native"] == 7.95
    assert r["product_name_raw"] == "Tulip Bulb Mix"
    assert r["category"] == "Bulbs"
    assert r["stock"] == 1
    assert r["product_code"] == "ABC-1"


def test_configurable_product_expands_to_one_row_per_variant():
    rows = _Probe().parse_records(_configurable_item(), "https://example.test/graphql")
    assert len(rows) == 2
    prices = sorted(r["price_native"] for r in rows)
    assert prices == [14.95, 24.95]
    sizes = sorted(r["size"] for r in rows)
    assert sizes == ["100 bulbs", "50 bulbs"]
    stocks = sorted((r["stock"] for r in rows), key=lambda v: (v is None, v))
    assert stocks == [0, 1]


def test_missing_price_drops_record():
    item = _simple_item()
    item["price_range"] = {}
    rows = _Probe().parse_records(item, "https://example.test/graphql")
    assert rows == []


def test_include_stock_status_toggle():
    with_stock = _build_list_query(include_stock=True)
    without_stock = _build_list_query(include_stock=False)
    assert "stock_status" in with_stock
    assert "stock_status" not in without_stock
