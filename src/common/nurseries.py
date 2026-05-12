"""Load and validate per-nursery metadata from config/nurseries.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "nurseries.yaml"

Currency = Literal["EUR", "GBP", "USD"]
DeliveryType = Literal["flat", "tiered", "by_weight", "quote_only", "free"]
RunsOn = Literal["github-actions", "self-hosted"]


class DeliveryFee(BaseModel):
    """One row in a tiered delivery schedule."""

    model_config = ConfigDict(frozen=True)

    max_value_eur: float | None = None
    fee_eur: float


class NurseryConfig(BaseModel):
    """Per-nursery metadata read from config/nurseries.yaml."""

    model_config = ConfigDict(frozen=True)

    display_name: str
    base_url: HttpUrl
    currency: Currency
    vat_included: bool
    delivery_type: DeliveryType
    delivery_fees: list[DeliveryFee] = Field(default_factory=list)
    min_order_eur: float = 0
    runs_on: RunsOn = "github-actions"
    ships_live_plants_to_ireland: bool = True
    notes: str = ""


def load_nurseries(path: Path | None = None) -> dict[str, NurseryConfig]:
    """Load and validate the nurseries config. Returns dict keyed by source slug."""

    config_path = path or CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return {slug: NurseryConfig.model_validate(cfg) for slug, cfg in raw.items()}


def scraped_nursery_slugs(path: Path | None = None) -> tuple[str, ...]:
    """Slugs of nurseries with a scraper today (``runs_on='github-actions'``).

    Self-hosted entries (farmer_gracy, bulbi, …) live in the yaml as planning
    placeholders without scrapers and are excluded from this list. This is the
    single source of truth for the freshness gate and the matching input loop.
    """
    cfgs = load_nurseries(path)
    return tuple(slug for slug, cfg in cfgs.items() if cfg.runs_on == "github-actions")
