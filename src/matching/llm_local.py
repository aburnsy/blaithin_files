"""LLM batch fallback against a local Ollama server.

Mirror of :mod:`src.matching.llm` but talks to a local Ollama instance over its
native HTTP API (default ``http://127.0.0.1:11434``). Ollama enforces the JSON
schema server-side via the ``format`` parameter so we never have to strip code
fences.

Default model is ``qwen3:14b`` (dense, 9GB Q4_K_M) running on the local GPU.
Override via ``OLLAMA_MODEL`` or the ``model=`` kwarg. The ``/no_think`` token
in the prompt disables Qwen3's reasoning trace for a ~10x throughput win on a
classification task like this one.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, get_args

import httpx
from pydantic import ValidationError

from src.common.logging import get_logger
from src.matching.models import MatchOverride, ProductCategory

log = get_logger("matching.llm_local")

# Smaller than the Claude path's 50: a local 14B model handles a tight prompt
# better than a long one, and a smaller batch means a smaller candidate union.
BATCH_SIZE = 10
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
# Qwen3 supports 40K natively; 32K covers our biggest realistic prompts with
# headroom for the response. KV cache at 32K is ~3-4 GB on top of ~9 GB weights,
# fits the 5080's 16 GB.
DEFAULT_NUM_CTX = 32768
_VALID_CATEGORIES: frozenset[str] = frozenset(get_args(ProductCategory))

SYSTEM_INSTRUCTIONS = (
    "You are a botanical name matcher. For each product string, you will be "
    "given a small shortlist of RHS plant records (id → {genus, species, "
    "common_names, synonyms}) that fuzzy-matched the batch's products. Return "
    "JSON ONLY (no prose) as an array. Each element must be:\n"
    '{"product_name_clean": str, "rhs_id": int|null, "cultivar": str|null, '
    '"is_plant": bool, "product_category": one of '
    '"plant"|"bulb"|"seed"|"compost"|"soil"|"tool"|"pot"|"fertiliser"|"accessory"|"other", '
    '"confidence": float in [0,1], "reasoning": str}\n'
    "Pick rhs_id ONLY from the provided shortlist. If none of the shortlisted "
    "records matches at the species level, set rhs_id=null. If the product is "
    "not a plant, set is_plant=false and pick the right category. If a plant "
    "has a cultivar in quotes, extract it."
)

# Ollama-side JSON schema. Server-enforced so we never have to strip fences.
_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "product_name_clean": {"type": "string"},
            "rhs_id": {"type": ["integer", "null"]},
            "cultivar": {"type": ["string", "null"]},
            "is_plant": {"type": "boolean"},
            "product_category": {
                "type": "string",
                "enum": list(get_args(ProductCategory)),
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
        },
        "required": [
            "product_name_clean",
            "rhs_id",
            "is_plant",
            "product_category",
        ],
    },
}


def _invoke_ollama(prompt: str, *, model: str, host: str, num_ctx: int) -> str:
    """POST to Ollama's /api/chat with server-enforced JSON schema."""
    resp = httpx.post(
        f"{host.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": _RESPONSE_SCHEMA,
            "stream": False,
            "think": False,  # disable Qwen3's reasoning trace — pure classification
            "options": {
                "temperature": 0,
                "num_ctx": num_ctx,
            },
        },
        timeout=httpx.Timeout(600.0),
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"ollama /api/chat returned {resp.status_code}: {resp.text[:500]}"
        )

    envelope = resp.json()
    msg = envelope.get("message") or {}
    content = msg.get("content")
    if not content:
        raise RuntimeError(f"ollama returned empty content: {envelope!r}")
    return content


def _build_override(
    raw: dict[str, Any],
    *,
    model: str,
    batch_idx: int,
) -> MatchOverride | None:
    """Coerce one Ollama-returned row into a MatchOverride.

    Same defensive coercion as src.matching.llm._build_override so the local
    backend slots into the existing persistence path unchanged.
    """
    if not isinstance(raw, dict) or "product_name_clean" not in raw:
        log.warning(
            "llm_row_dropped",
            batch=batch_idx,
            reason="missing_product_name_clean",
            row=raw,
        )
        return None

    category = raw.get("product_category") or "other"
    if category not in _VALID_CATEGORIES:
        log.warning(
            "llm_category_coerced",
            batch=batch_idx,
            product_name_clean=raw.get("product_name_clean"),
            received=category,
        )
        category = "other"

    rhs_id_raw = raw.get("rhs_id")
    try:
        rhs_id = int(rhs_id_raw) if rhs_id_raw is not None else None
    except (TypeError, ValueError):
        rhs_id = None

    is_plant_raw = raw.get("is_plant", False)
    is_plant = (
        bool(is_plant_raw)
        if not isinstance(is_plant_raw, str)
        else is_plant_raw.strip().lower() == "true"
    )

    try:
        return MatchOverride(
            product_name_clean=str(raw["product_name_clean"]),
            rhs_id=rhs_id,
            cultivar=raw.get("cultivar"),
            is_plant=is_plant,
            product_category=category,
            source="llm",
            model=model,
            notes=raw.get("reasoning"),
        )
    except ValidationError as e:
        log.warning(
            "llm_row_dropped",
            batch=batch_idx,
            reason="validation_error",
            product_name_clean=raw.get("product_name_clean"),
            error=str(e),
        )
        return None


def batch_resolve(
    unmatched_clean_names: list[str],
    candidates_per_name: dict[str, list[int]],
    rhs_lookup: dict[int, dict[str, Any]],
    *,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    num_ctx: int = DEFAULT_NUM_CTX,
    api_key: str | None = None,  # accepted for signature compat; unused
    on_batch_complete: Callable[[list[MatchOverride]], None] | None = None,
    concurrency: int = 1,
) -> list[MatchOverride]:
    """Resolve unmatched product names via local Ollama. Signature matches
    :func:`src.matching.llm.batch_resolve` so callers swap freely.

    Args:
        unmatched_clean_names: cleaned product names the deterministic pipeline missed.
        candidates_per_name: ``{name_lower: [rhs_id, ...]}`` shortlist per product
            (built by :func:`src.matching.fuzzy.top_k_candidates_per_query`).
        rhs_lookup: ``{rhs_id: {genus, species, common_names, synonyms}}``.
        model: Ollama model tag. Default ``qwen3:14b``.
        host: Ollama base URL. Default ``http://127.0.0.1:11434``.
        num_ctx: context window passed to Ollama. 8192 fits 50 products + ~30-50
            candidates comfortably; bump for larger batches or shortlists.
        api_key: ignored; kept so existing callers don't need to change.
        on_batch_complete: optional callback invoked after each successful batch
            with the produced ``MatchOverride`` records. Caller persists state.
        concurrency: in-flight batches. Ollama serialises per-model anyway, so
            >1 mainly helps if you point at a remote multi-GPU host.
    """
    del api_key

    if concurrency < 1:
        raise ValueError(f"concurrency must be >= 1, got {concurrency}")

    total = len(unmatched_clean_names)
    n_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    log.info(
        "batch_resolve_start",
        products=total,
        batches=n_batches,
        batch_size=BATCH_SIZE,
        model=model,
        host=host,
        rhs_lookup_size=len(rhs_lookup),
        concurrency=concurrency,
    )

    batch_specs: list[tuple[int, list[str], dict[int, dict[str, Any]], str]] = []
    for batch_idx, chunk_start in enumerate(range(0, total, BATCH_SIZE), start=1):
        chunk = unmatched_clean_names[chunk_start : chunk_start + BATCH_SIZE]
        batch_ids: set[int] = set()
        for name in chunk:
            for rid in candidates_per_name.get(name.lower(), []):
                batch_ids.add(rid)
        batch_candidates = {
            rid: rhs_lookup[rid] for rid in batch_ids if rid in rhs_lookup
        }
        candidate_block = json.dumps(batch_candidates, separators=(",", ":"))
        prompt = (
            f"{SYSTEM_INSTRUCTIONS}\n\n"
            f"RHS candidates: {candidate_block}\n\n"
            f"Products to match:\n{json.dumps(chunk)}"
        )
        batch_specs.append((batch_idx, chunk, batch_candidates, prompt))

    overrides: list[MatchOverride] = []
    started = time.monotonic()
    candidate_count_sum = 0
    prompt_bytes_sum = 0

    def _run_one(spec):
        batch_idx, chunk, batch_candidates, prompt = spec
        t0 = time.monotonic()
        text = _invoke_ollama(prompt, model=model, host=host, num_ctx=num_ctx)
        return batch_idx, chunk, batch_candidates, prompt, text, time.monotonic() - t0

    def _handle_result(result) -> None:
        nonlocal candidate_count_sum, prompt_bytes_sum
        batch_idx, chunk, batch_candidates, prompt, text, batch_elapsed = result
        candidate_count_sum += len(batch_candidates)
        prompt_bytes_sum += len(prompt)

        try:
            rows = json.loads(text)
        except json.JSONDecodeError as e:
            log.error(
                "llm_batch_non_json",
                batch=batch_idx,
                error=str(e),
                text=text[:500],
            )
            return

        batch_overrides: list[MatchOverride] = []
        for r in rows:
            ov = _build_override(r, model=model, batch_idx=batch_idx)
            if ov is not None:
                batch_overrides.append(ov)
        overrides.extend(batch_overrides)

        if on_batch_complete is not None:
            try:
                on_batch_complete(batch_overrides)
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "on_batch_complete_failed",
                    batch=batch_idx,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

        log.info(
            "batch_resolved",
            batch=batch_idx,
            of=n_batches,
            chunk_size=len(chunk),
            candidates=len(batch_candidates),
            prompt_kb=round(len(prompt) / 1024, 1),
            resolved_in_batch=len(batch_overrides),
            received_in_batch=len(rows),
            cumulative=len(overrides),
            batch_s=round(batch_elapsed, 1),
            elapsed_s=round(time.monotonic() - started, 1),
        )

    if concurrency == 1:
        for spec in batch_specs:
            _handle_result(_run_one(spec))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = [ex.submit(_run_one, spec) for spec in batch_specs]
            for fut in as_completed(futures):
                _handle_result(fut.result())

    log.info(
        "batch_resolve_done",
        products=total,
        overrides=len(overrides),
        avg_candidates_per_batch=round(candidate_count_sum / max(1, n_batches), 1),
        avg_prompt_kb=round(prompt_bytes_sum / max(1, n_batches) / 1024, 1),
        elapsed_s=round(time.monotonic() - started, 1),
    )
    return overrides
