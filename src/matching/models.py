"""Pydantic v2 models for the matching pipeline.

These models define the shape of every record that flows between the matching
modules (parsers, matchers, classifiers, LLM, persistence). Keeping them in one
file makes the pipeline's data contract easy to read end-to-end.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

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
    cultivar: Optional[str] = None
    cultivar_group: Optional[str] = None
    rank: Optional[str] = None  # e.g. "var.", "subsp."
    raw: Optional[str] = None  # original input string for debugging


class MatchResult(BaseModel):
    """Output of any of the matchers."""

    model_config = ConfigDict(frozen=True)

    rhs_id: Optional[int] = None
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
    family: Optional[str] = None
    description: Optional[str] = None
    is_rhs_award_winner: bool = False
    is_pollinator_plant: bool = False
    height: Optional[str] = None
    spread: Optional[str] = None
    soils: list[str] = Field(default_factory=list)
    moisture: Optional[str] = None
    ph: list[str] = Field(default_factory=list)
    sun_exposure: list[str] = Field(default_factory=list)
    aspect: list[str] = Field(default_factory=list)
    exposure: list[str] = Field(default_factory=list)
    hardiness: Optional[str] = None
    foliage: list[str] = Field(default_factory=list)
    habit: list[str] = Field(default_factory=list)
    plant_url: Optional[str] = None


class ProductRecord(BaseModel):
    """A single nursery product row, post-matching."""

    source: str
    product_url: str
    source_url: Optional[str] = None
    category: Optional[str] = None
    product_name_raw: str
    product_name_clean: str
    genus: Optional[str] = None
    species: Optional[str] = None
    cultivar: Optional[str] = None
    cultivar_group: Optional[str] = None
    rhs_id: Optional[int] = None
    match_method: MatchMethod = "unmatched"
    match_confidence: float = 0.0
    is_plant: bool = True
    product_category: ProductCategory = "plant"
    price_native: Optional[float] = None
    currency: str = "EUR"
    price_eur: Optional[float] = None
    size: Optional[str] = None
    pot_size_litres: Optional[float] = None
    stock: Optional[int] = None
    quantity_per_pack: int = 1
    img_url: Optional[str] = None
    description: Optional[str] = None
    input_date: Optional[datetime] = None


class MatchOverride(BaseModel):
    """A single row in `data/match_overrides.parquet`."""

    product_name_clean: str
    rhs_id: Optional[int] = None
    cultivar: Optional[str] = None
    is_plant: bool = True
    product_category: ProductCategory = "plant"
    source: Literal["llm", "manual"]
    model: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
