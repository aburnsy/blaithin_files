"""Pydantic v2 models for the matching pipeline.

These models define the shape of every record that flows between the matching
modules (parsers, matchers, classifiers, LLM, persistence). Keeping them in one
file makes the pipeline's data contract easy to read end-to-end.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MatchMethod = Literal[
    "url_field",
    "gnparser_exact",
    "rapidfuzz",
    "llm",
    "manual_override",
    "unmatched",
]

ProductCategory = Literal[
    "plant",
    "bulb",
    "seed",
    "compost",
    "soil",
    "tool",
    "pot",
    "fertiliser",
    "accessory",
    "other",
]


class ParsedName(BaseModel):
    """Output of `gnparser_wrap.parse(...)`: a botanical name decomposed."""

    model_config = ConfigDict(frozen=True)

    genus: str
    species: str
    cultivar: str | None = None
    cultivar_group: str | None = None
    rank: str | None = None  # e.g. "var.", "subsp."
    raw: str | None = None  # original input string for debugging


class MatchResult(BaseModel):
    """Output of any of the matchers."""

    model_config = ConfigDict(frozen=True)

    rhs_id: int | None = None
    method: MatchMethod
    confidence: float = Field(ge=0.0, le=1.0)


class RhsRecord(BaseModel):
    """A single RHS plant record (re-modelled — synonyms[] preserved)."""

    rhs_id: int
    genus: str
    species: str
    botanical_name: str
    common_names: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    plant_type: list[str] = Field(default_factory=list)
    family: str | None = None
    description: str | None = None
    is_rhs_award_winner: bool = False
    is_pollinator_plant: bool = False
    height: str | None = None
    spread: str | None = None
    soils: list[str] = Field(default_factory=list)
    moisture: str | None = None
    ph: list[str] = Field(default_factory=list)
    sun_exposure: list[str] = Field(default_factory=list)
    aspect: list[str] = Field(default_factory=list)
    exposure: list[str] = Field(default_factory=list)
    hardiness: str | None = None
    foliage: list[str] = Field(default_factory=list)
    habit: list[str] = Field(default_factory=list)
    plant_url: str | None = None


class ProductRecord(BaseModel):
    """A single nursery product row, post-matching."""

    source: str
    product_url: str
    source_url: str | None = None
    category: str | None = None
    product_name_raw: str
    product_name_clean: str
    genus: str | None = None
    species: str | None = None
    cultivar: str | None = None
    cultivar_group: str | None = None
    rhs_id: int | None = None
    match_method: MatchMethod = "unmatched"
    match_confidence: float = 0.0
    is_plant: bool = True
    product_category: ProductCategory = "plant"
    price_native: float | None = None
    currency: str = "EUR"
    price_eur: float | None = None
    size: str | None = None
    pot_size_litres: float | None = None
    stock: int | None = None
    quantity_per_pack: int = 1
    img_url: str | None = None
    description: str | None = None
    input_date: datetime | None = None


class MatchOverride(BaseModel):
    """A single row in `data/match_overrides.parquet`."""

    product_name_clean: str
    rhs_id: int | None = None
    cultivar: str | None = None
    is_plant: bool = True
    product_category: ProductCategory = "plant"
    source: Literal["llm", "manual"]
    model: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    notes: str | None = None
