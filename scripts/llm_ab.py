"""A/B-test the local Ollama LLM backend against the historical Claude results.

Takes a sample of product names from a past resolutions audit log, replays them
through :func:`src.matching.llm_local.batch_resolve`, and compares the local
backend's rhs_id assignments against Claude's. Reports agreement rate,
disagreement examples, and per-batch throughput.

Usage:
    python scripts/llm_ab.py                       # default: 200-name sample, latest audit log
    python scripts/llm_ab.py --sample 500
    python scripts/llm_ab.py --audit data/llm_audit/resolutions_20260515T073117Z.jsonl
    python scripts/llm_ab.py --model qwen3:14b    # override the local model tag
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import polars as pl  # noqa: E402

from src.common.logging import configure as configure_logging  # noqa: E402
from src.common.logging import get_logger  # noqa: E402
from src.matching.fuzzy import (  # noqa: E402
    LLM_CANDIDATE_K,
    LLM_CANDIDATE_THRESHOLD,
    top_k_candidates_per_query,
)
from src.matching.llm_local import DEFAULT_MODEL, batch_resolve  # noqa: E402

RHS_PATH = Path("data/rhs/data.parquet")
AUDIT_DIR = Path("data/llm_audit")


def _latest_audit_log() -> Path:
    candidates = sorted(AUDIT_DIR.glob("resolutions_*.jsonl"))
    if not candidates:
        raise SystemExit(f"no audit logs found under {AUDIT_DIR}")
    return candidates[-1]


def _load_claude_decisions(path: Path) -> dict[str, dict]:
    """Return {product_name_clean: latest_claude_row}. Later rows shadow earlier."""
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out[row["product_name_clean"]] = row
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=None,
                        help="audit jsonl to replay; default = newest in data/llm_audit/")
    parser.add_argument("--sample", type=int, default=200,
                        help="how many distinct names to replay (default 200)")
    parser.add_argument("--seed", type=int, default=42, help="rng seed")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"local model tag (default {DEFAULT_MODEL})")
    parser.add_argument("--report", type=Path,
                        default=Path("data/llm_audit/ab_report.tsv"),
                        help="path to write the side-by-side report")
    args = parser.parse_args()

    configure_logging(source="llm_ab", force=True)
    log = get_logger("llm_ab")

    audit_path = args.audit or _latest_audit_log()
    log.info("audit_log_chosen", path=str(audit_path))

    claude = _load_claude_decisions(audit_path)
    log.info("audit_loaded", unique_names=len(claude))

    names = sorted(claude.keys())
    random.Random(args.seed).shuffle(names)
    sample = names[: args.sample]
    log.info("sample_drawn", n=len(sample))

    if not RHS_PATH.exists():
        raise SystemExit(f"missing RHS at {RHS_PATH}")
    rhs_df = pl.read_parquet(RHS_PATH)

    # Build the per-name shortlist exactly as the production pipeline does.
    t0 = time.monotonic()
    cands = top_k_candidates_per_query(
        sample, rhs_df, k=LLM_CANDIDATE_K, threshold=LLM_CANDIDATE_THRESHOLD,
    )
    log.info("candidates_built", elapsed_s=round(time.monotonic() - t0, 1))

    needed_ids: set[int] = set()
    for ids in cands.values():
        needed_ids.update(ids)
    id_col = "rhs_id" if "rhs_id" in rhs_df.columns else "id"
    subset = (
        rhs_df.filter(pl.col(id_col).is_in(list(needed_ids)))
        if needed_ids
        else rhs_df.head(0)
    )
    rhs_lookup: dict[int, dict] = {}
    for row in subset.iter_rows(named=True):
        bn = row.get("botanical_name") or ""
        parts = bn.split(" ", 1) if bn else ["", ""]
        rhs_lookup[row[id_col]] = {
            "genus": parts[0],
            "species": parts[1].strip("'\"") if len(parts) > 1 else "",
            "common_names": [row["common_name"]] if row.get("common_name") else [],
            "synonyms": row.get("synonyms") or [],
        }
    log.info("rhs_lookup_built", count=len(rhs_lookup))

    t0 = time.monotonic()
    local_overrides = batch_resolve(sample, cands, rhs_lookup, model=args.model)
    local_elapsed = time.monotonic() - t0
    log.info(
        "local_batch_done",
        overrides=len(local_overrides),
        elapsed_s=round(local_elapsed, 1),
        names_per_s=round(len(sample) / max(local_elapsed, 1e-6), 1),
    )

    local_by_name = {ov.product_name_clean: ov for ov in local_overrides}

    rows: list[dict] = []
    agree = 0
    both_picked = 0
    local_picked = 0
    claude_picked = 0
    neither = 0
    for name in sample:
        c_row = claude[name]
        c_rhs = c_row.get("rhs_id")
        ov = local_by_name.get(name)
        l_rhs = ov.rhs_id if ov else None

        if c_rhs is not None and l_rhs is not None:
            both_picked += 1
            if c_rhs == l_rhs:
                agree += 1
        if l_rhs is not None:
            local_picked += 1
        if c_rhs is not None:
            claude_picked += 1
        if c_rhs is None and l_rhs is None:
            neither += 1

        rows.append({
            "product_name_clean": name,
            "claude_rhs_id": c_rhs,
            "local_rhs_id": l_rhs,
            "agree": (c_rhs == l_rhs),
            "claude_is_plant": c_row.get("is_plant"),
            "local_is_plant": ov.is_plant if ov else None,
            "claude_category": c_row.get("product_category"),
            "local_category": ov.product_category if ov else None,
            "claude_notes": (c_row.get("notes") or "")[:120],
            "local_notes": (ov.notes or "")[:120] if ov else "",
        })

    report_df = pl.DataFrame(rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report_df.write_csv(args.report, separator="\t")

    overall_agree_pct = 100 * agree / max(both_picked, 1)
    log.info(
        "ab_summary",
        sample=len(sample),
        both_picked=both_picked,
        agree_when_both_picked=agree,
        agree_pct=round(overall_agree_pct, 1),
        local_picked=local_picked,
        claude_picked=claude_picked,
        neither_picked=neither,
        local_latency_s=round(local_elapsed, 1),
        report=str(args.report),
    )

    disagreements = report_df.filter(~pl.col("agree")).head(10)
    log.info("disagreement_sample", rows=disagreements.to_dicts())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
