# TODO

## Matching: add a semantic-embedding tier before the LLM fallback

**Why:** Right now the deterministic pipeline (override cache → exact → fuzzy/gnparser) drops everything it can't crack straight onto the `claude -p` LLM tier. A lot of that residual is common-name / synonym matches that a small sentence-embedding model would handle deterministically, locally, and for free — pushing LLM cost (and latency) down further.

**Sketch:**
- One-off: build an embedding index over `botanical_name + common_names + synonyms` for every RHS row, cache to `data/rhs/embeddings.parquet`. Model candidate: `sentence-transformers/all-MiniLM-L6-v2` (~80MB, CPU-fast, no GPU needed).
- New pipeline step `src/matching/semantic.py` between `fuzzy_match` and the unmatched LLM fallback: embed each unmatched `product_name_clean`, cosine-rank against the cached RHS index, accept top-1 if score > threshold (tune on the override cache as ground truth).
- LLM stays as the final safety net for whatever embeddings still can't resolve — cultivar trade names, multi-language entries, noisy retail copy.

**Acceptance:**
- The `match_method_breakdown` log gains a `semantic` bucket.
- Measurable drop in rows hitting the `llm` bucket on a full re-run, with no regression in correctness on `tests/fixtures/match_overrides.parquet`.
- Embeddings model + index rebuild is reproducible from a single script and the index is gitignored (or stored alongside `data/rhs/data.parquet`).

**Not doing (yet):**
- Replacing the LLM tier entirely with a local LLM (Ollama/Qwen/Phi). Worse accuracy on the hard tail and the override cache already amortises LLM cost over time.
