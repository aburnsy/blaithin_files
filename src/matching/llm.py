"""LLM batch fallback for unmatched products via the Claude CLI (`claude -p`).

Runs against the Claude Agent SDK credit pool included with the Max
subscription (separate from interactive subscription limits). Requires the
``claude`` CLI to be on PATH — same binary that powers Claude Code.

Each call resolves up to ``BATCH_SIZE`` products. The candidate set for each
batch is the **union of top-K RHS records** across the batch's products — built
upstream by :func:`src.matching.fuzzy.top_k_candidates_per_query`. This keeps
each prompt in the KB range instead of MB.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, get_args

from pydantic import ValidationError

from src.common.logging import get_logger
from src.matching.models import MatchOverride, ProductCategory

log = get_logger("matching.llm")

BATCH_SIZE = 50
MODEL = "claude-haiku-4-5-20251001"
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


def _claude_cli() -> str:
    path = shutil.which("claude") or shutil.which("claude.cmd")
    if not path:
        raise RuntimeError(
            "`claude` CLI not found on PATH — install Claude Code or add it to PATH."
        )
    return path


def _strip_code_fence(text: str) -> str:
    """Strip a leading/trailing ```json ... ``` fence if Claude wrapped its output."""
    s = text.strip()
    if not s.startswith("```"):
        return s
    s = s[3:]
    if s.lower().startswith("json"):
        s = s[4:]
    s = s.lstrip("\r\n")
    if s.endswith("```"):
        s = s[:-3]
    return s.strip()


def _invoke_claude(prompt: str, *, model: str) -> str:
    """Run ``claude -p`` headlessly and return the assistant's text body."""
    proc = subprocess.run(
        [
            _claude_cli(),
            "-p",
            "--model", model,
            "--output-format", "json",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude -p exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"claude -p returned non-JSON: {proc.stdout[:500]!r}") from e

    if envelope.get("is_error") or envelope.get("subtype") != "success":
        raise RuntimeError(f"claude -p reported failure: {envelope!r}")

    return envelope["result"]


def _build_override(
    raw: dict[str, Any],
    *,
    model: str,
    batch_idx: int,
) -> MatchOverride | None:
    """Coerce one Claude-returned row into a :class:`MatchOverride`.

    Unknown ``product_category`` values (e.g. "succulent") are coerced to
    ``"other"`` rather than crashing the batch — Claude occasionally invents
    categories that aren't in our Literal. ``rhs_id`` is coerced to int|None
    and ``is_plant`` to bool. Rows that still fail pydantic validation are
    logged and dropped.
    """
    if not isinstance(raw, dict) or "product_name_clean" not in raw:
        log.warning("llm_row_dropped", batch=batch_idx, reason="missing_product_name_clean", row=raw)
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
    is_plant = bool(is_plant_raw) if not isinstance(is_plant_raw, str) else is_plant_raw.strip().lower() == "true"

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
    model: str = MODEL,
    api_key: str | None = None,  # accepted for signature compat; unused
    on_batch_complete: Callable[[list[MatchOverride]], None] | None = None,
    concurrency: int = 1,
) -> list[MatchOverride]:
    """Resolve unmatched product names via Claude Haiku through ``claude -p``.

    Args:
        unmatched_clean_names: cleaned product names the deterministic pipeline missed.
        candidates_per_name: ``{name_lower: [rhs_id, ...]}`` shortlist per product,
            built upstream by :func:`src.matching.fuzzy.top_k_candidates_per_query`.
            Names absent from this dict (or mapped to an empty list) are sent to
            the LLM with no shortlist — useful for non-plant classification.
        rhs_lookup: ``{rhs_id: {genus, species, common_names, synonyms}}`` — only
            needs to contain the union of rhs_ids that appear in ``candidates_per_name``.
        model: anthropic model id (passed to ``claude --model``).
        api_key: ignored — kept so existing callers don't need to change.
        on_batch_complete: optional callback fired after each successful batch
            with the list of ``MatchOverride`` records produced by that batch.
            The caller can use this to persist progress incrementally so a crash
            mid-run doesn't waste prior LLM credits. Exceptions inside the
            callback are logged and swallowed — they do not abort the run.
        concurrency: number of in-flight ``claude -p`` subprocesses. Default 1
            (serial). Each worker is its own process; the persistence callback
            is always invoked on the main thread so it doesn't need locking.

    Returns:
        List of ``MatchOverride`` records ready for persistence.
    """
    del api_key  # no-op; transport is `claude -p`

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
        rhs_lookup_size=len(rhs_lookup),
        concurrency=concurrency,
    )

    # Pre-build every batch spec so the worker function is a pure I/O call.
    batch_specs: list[tuple[int, list[str], dict[int, dict[str, Any]], str]] = []
    for batch_idx, chunk_start in enumerate(range(0, total, BATCH_SIZE), start=1):
        chunk = unmatched_clean_names[chunk_start : chunk_start + BATCH_SIZE]
        batch_ids: set[int] = set()
        for name in chunk:
            for rid in candidates_per_name.get(name.lower(), []):
                batch_ids.add(rid)
        batch_candidates = {rid: rhs_lookup[rid] for rid in batch_ids if rid in rhs_lookup}
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

    def _run_one(spec: tuple[int, list[str], dict[int, dict[str, Any]], str]):
        batch_idx, chunk, batch_candidates, prompt = spec
        t0 = time.monotonic()
        text = _invoke_claude(prompt, model=model)
        return batch_idx, chunk, batch_candidates, prompt, text, time.monotonic() - t0

    def _handle_result(result) -> None:
        nonlocal candidate_count_sum, prompt_bytes_sum
        batch_idx, chunk, batch_candidates, prompt, text, batch_elapsed = result
        candidate_count_sum += len(batch_candidates)
        prompt_bytes_sum += len(prompt)

        try:
            rows = json.loads(_strip_code_fence(text))
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
            except Exception as exc:  # noqa: BLE001 — never abort the run on a persistence hiccup
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
