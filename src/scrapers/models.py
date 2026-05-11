"""Scraper-side raw product record (pre-matching)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RawProduct(BaseModel):
    """A raw product row produced by a scraper, before matching pipeline runs."""

    model_config = ConfigDict(extra="allow")

    source: str
    product_url: str
    source_url: str | None = None
    category: str | None = None
    product_name_raw: str
    price_native: float | None = None
    currency: str = "EUR"
    size: str | None = None
    stock: int | None = None
    quantity_per_pack: int = 1
    img_url: str | None = None
    description: str | None = None


def validate_record(record: dict) -> RawProduct:
    """Validate a dict produced by a scraper. Raises ValidationError on failure."""
    return RawProduct.model_validate(record)
