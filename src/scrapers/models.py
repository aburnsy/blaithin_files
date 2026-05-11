"""Scraper-side raw product record (pre-matching)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class RawProduct(BaseModel):
    """A raw product row produced by a scraper, before matching pipeline runs."""

    model_config = ConfigDict(extra="allow")

    source: str
    product_url: str
    source_url: Optional[str] = None
    category: Optional[str] = None
    product_name_raw: str
    price_native: Optional[float] = None
    currency: str = "EUR"
    size: Optional[str] = None
    stock: Optional[int] = None
    quantity_per_pack: int = 1
    img_url: Optional[str] = None
    description: Optional[str] = None


def validate_record(record: dict) -> RawProduct:
    """Validate a dict produced by a scraper. Raises ValidationError on failure."""
    return RawProduct.model_validate(record)
