"""LLM batch fallback for unmatched products, using Claude Haiku 4.5 with prompt caching.

The RHS candidate list is sent as a CACHED system prefix so subsequent calls within
the cache TTL hit cheap. Each call resolves up to BATCH_SIZE products at once.
"""

from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic

from src.matching.models import MatchOverride

BATCH_SIZE = 50
MODEL = "claude-haiku-4-5-20251001"


def batch_resolve(
    unmatched_clean_names: list[str],
    rhs_candidates: dict[int, dict[str, Any]],
    *,
    model: str = MODEL,
    api_key: str | None = None,
) -> list[MatchOverride]:
    """Resolve unmatched product names via Claude Haiku.

    Args:
        unmatched_clean_names: cleaned product names that the deterministic pipeline missed.
        rhs_candidates: dict[rhs_id, {genus, species, common_names, synonyms}] subset of RHS
            relevant to these products. Caller is responsible for narrowing this — the full
            62k RHS table is too large to send.
        model: anthropic model id.
        api_key: optional override; defaults to ANTHROPIC_API_KEY env var.

    Returns:
        List of MatchOverride records ready to be persisted via overrides.upsert_override.
    """

    client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    candidate_block = json.dumps(rhs_candidates, indent=None, separators=(",", ":"))

    overrides: list[MatchOverride] = []
    for chunk_start in range(0, len(unmatched_clean_names), BATCH_SIZE):
        chunk = unmatched_clean_names[chunk_start : chunk_start + BATCH_SIZE]
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": (
                        "You are a botanical name matcher. Given a list of RHS plant records "
                        "(id → {genus, species, common_names, synonyms}) and a list of unmatched "
                        "product strings from Irish/UK nurseries, return JSON ONLY (no prose) "
                        "as an array. Each element must be:\n"
                        '{"product_name_clean": str, "rhs_id": int|null, "cultivar": str|null, '
                        '"is_plant": bool, "product_category": one of '
                        '"plant"|"bulb"|"seed"|"compost"|"soil"|"tool"|"pot"|"fertiliser"|"accessory"|"other", '
                        '"confidence": float in [0,1], "reasoning": str}\n'
                        "If product is not a plant, set is_plant=false and pick the right category. "
                        "If a plant has a cultivar in quotes, extract it. If no RHS record matches "
                        "at species level, set rhs_id=null."
                    ),
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": f"RHS candidates: {candidate_block}",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Products to match:\n{json.dumps(chunk)}",
                }
            ],
        )
        text = message.content[0].text
        results = json.loads(text)
        for r in results:
            overrides.append(
                MatchOverride(
                    product_name_clean=r["product_name_clean"],
                    rhs_id=r.get("rhs_id"),
                    cultivar=r.get("cultivar"),
                    is_plant=r.get("is_plant", False),
                    product_category=r.get("product_category", "other"),
                    source="llm",
                    model=model,
                    notes=r.get("reasoning"),
                )
            )

    return overrides
