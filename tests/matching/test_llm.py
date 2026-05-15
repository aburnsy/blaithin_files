"""Tests for the LLM batch resolver (with mocked `claude -p` invocation)."""

import json
import threading
import time
from unittest.mock import patch

from src.matching.llm import BATCH_SIZE, batch_resolve
from src.matching.models import MatchOverride


@patch("src.matching.llm._invoke_claude")
def test_batch_resolve_returns_overrides(mock_invoke):
    mock_invoke.return_value = (
        '[{"product_name_clean":"acer palmatum bloodgood","rhs_id":12345,'
        '"cultivar":"Bloodgood","is_plant":true,"product_category":"plant",'
        '"confidence":0.95,"reasoning":"clear cultivar"}]'
    )
    candidates_per_name = {"acer palmatum bloodgood": [12345]}
    rhs_lookup = {12345: {"genus": "Acer", "species": "palmatum", "common_names": ["Japanese Maple"], "synonyms": []}}
    overrides = batch_resolve(["acer palmatum bloodgood"], candidates_per_name, rhs_lookup)
    assert len(overrides) == 1
    assert isinstance(overrides[0], MatchOverride)
    assert overrides[0].rhs_id == 12345
    assert overrides[0].cultivar == "Bloodgood"
    assert overrides[0].source == "llm"


@patch("src.matching.llm._invoke_claude")
def test_batch_resolve_handles_no_match(mock_invoke):
    mock_invoke.return_value = (
        '[{"product_name_clean":"unknown thing","rhs_id":null,"is_plant":false,'
        '"product_category":"other","confidence":0.5,"reasoning":"not a plant"}]'
    )
    overrides = batch_resolve(["unknown thing"], {}, {})
    assert overrides[0].rhs_id is None
    assert overrides[0].is_plant is False
    assert overrides[0].product_category == "other"


@patch("src.matching.llm._invoke_claude")
def test_per_batch_candidate_block_is_subset(mock_invoke):
    """The candidate block sent to claude must only contain rhs_ids
    referenced by the batch's products — not the full rhs_lookup."""
    captured_prompts: list[str] = []

    def capture(prompt, *, model):
        captured_prompts.append(prompt)
        # Return one valid result per product in the batch so loop completes.
        # Parse the batch products out of the prompt and synthesise a reply.
        products = json.loads(prompt.split("Products to match:\n", 1)[1])
        return json.dumps([
            {
                "product_name_clean": p,
                "rhs_id": None,
                "is_plant": False,
                "product_category": "other",
                "confidence": 0.5,
                "reasoning": "test",
            }
            for p in products
        ])

    mock_invoke.side_effect = capture

    candidates_per_name = {
        "acer palmatum": [10, 20],
        "hosta sieboldiana": [30],
        # "unrelated rake" intentionally absent — empty shortlist for it
    }
    rhs_lookup = {
        10: {"genus": "Acer", "species": "palmatum"},
        20: {"genus": "Acer", "species": "palmatum", "common_names": ["maple"]},
        30: {"genus": "Hosta", "species": "sieboldiana"},
        99: {"genus": "Other", "species": "thing"},  # MUST NOT appear in any prompt
    }
    batch_resolve(
        ["acer palmatum", "hosta sieboldiana", "unrelated rake"],
        candidates_per_name,
        rhs_lookup,
    )

    assert len(captured_prompts) == 1
    candidate_block = captured_prompts[0].split("RHS candidates: ", 1)[1].split("\n", 1)[0]
    parsed = json.loads(candidate_block)
    assert set(parsed.keys()) == {"10", "20", "30"}  # 99 excluded; integer keys serialised as str


@patch("src.matching.llm._invoke_claude")
def test_multiple_batches_split_candidate_blocks(mock_invoke):
    """Each batch gets its own candidate subset; one batch's ids don't leak into another's."""
    captured_prompts: list[str] = []

    def capture(prompt, *, model):
        captured_prompts.append(prompt)
        products = json.loads(prompt.split("Products to match:\n", 1)[1])
        return json.dumps([
            {"product_name_clean": p, "rhs_id": None, "is_plant": False, "product_category": "other", "confidence": 0.5, "reasoning": ""}
            for p in products
        ])

    mock_invoke.side_effect = capture

    # Two batches by name; first has only id=1, second has only id=2
    names_batch1 = [f"name_a_{i}" for i in range(BATCH_SIZE)]
    names_batch2 = [f"name_b_{i}" for i in range(5)]
    candidates_per_name = {n: [1] for n in names_batch1}
    candidates_per_name.update({n: [2] for n in names_batch2})
    rhs_lookup = {
        1: {"genus": "A", "species": "a"},
        2: {"genus": "B", "species": "b"},
    }
    batch_resolve(names_batch1 + names_batch2, candidates_per_name, rhs_lookup)

    assert len(captured_prompts) == 2
    cb1 = json.loads(captured_prompts[0].split("RHS candidates: ", 1)[1].split("\n", 1)[0])
    cb2 = json.loads(captured_prompts[1].split("RHS candidates: ", 1)[1].split("\n", 1)[0])
    assert set(cb1.keys()) == {"1"}
    assert set(cb2.keys()) == {"2"}


@patch("src.matching.llm._invoke_claude")
def test_on_batch_complete_fires_per_batch(mock_invoke):
    """The callback must receive each batch's overrides as it completes."""

    def reply(prompt, *, model):
        products = json.loads(prompt.split("Products to match:\n", 1)[1])
        return json.dumps([
            {"product_name_clean": p, "rhs_id": None, "is_plant": False, "product_category": "other", "confidence": 0.5, "reasoning": ""}
            for p in products
        ])

    mock_invoke.side_effect = reply

    seen: list[list[MatchOverride]] = []
    names = [f"name_{i}" for i in range(BATCH_SIZE + 3)]  # 2 batches
    result = batch_resolve(
        names,
        {},
        {},
        on_batch_complete=lambda batch: seen.append(batch),
    )
    assert len(seen) == 2
    assert len(seen[0]) == BATCH_SIZE
    assert len(seen[1]) == 3
    assert sum(len(b) for b in seen) == len(result)


@patch("src.matching.llm._invoke_claude")
def test_on_batch_complete_exception_does_not_abort_run(mock_invoke):
    """A buggy callback should not crash the LLM run — it should be logged and skipped."""

    def reply(prompt, *, model):
        products = json.loads(prompt.split("Products to match:\n", 1)[1])
        return json.dumps([
            {"product_name_clean": p, "rhs_id": None, "is_plant": False, "product_category": "other", "confidence": 0.5, "reasoning": ""}
            for p in products
        ])

    mock_invoke.side_effect = reply

    def boom(batch):
        raise OSError("disk gone")

    result = batch_resolve(
        ["alpha", "beta"],
        {},
        {},
        on_batch_complete=boom,
    )
    # batch_resolve completed despite the callback failure
    assert len(result) == 2


@patch("src.matching.llm._invoke_claude")
def test_unknown_product_category_is_coerced_to_other(mock_invoke):
    """Claude occasionally returns categories outside the Literal (e.g. 'succulent').
    These must be coerced to 'other' rather than crashing the batch."""
    mock_invoke.return_value = json.dumps(
        [
            {
                "product_name_clean": "echeveria gibbiflora",
                "rhs_id": None,
                "is_plant": True,
                "product_category": "succulent",  # not in the Literal
                "confidence": 0.7,
                "reasoning": "",
            }
        ]
    )
    overrides = batch_resolve(["echeveria gibbiflora"], {}, {})
    assert len(overrides) == 1
    assert overrides[0].product_category == "other"
    assert overrides[0].is_plant is True


@patch("src.matching.llm._invoke_claude")
def test_invalid_row_skipped_without_losing_batch(mock_invoke):
    """One unparseable row in a batch must not lose the other rows."""
    mock_invoke.return_value = json.dumps(
        [
            {
                "product_name_clean": "good plant",
                "rhs_id": 1,
                "is_plant": True,
                "product_category": "plant",
                "confidence": 0.9,
            },
            {
                # Missing product_name_clean — this row should be dropped.
                "rhs_id": 2,
                "is_plant": True,
                "product_category": "plant",
                "confidence": 0.9,
            },
            {
                "product_name_clean": "another good plant",
                "rhs_id": 3,
                "is_plant": True,
                "product_category": "plant",
                "confidence": 0.9,
            },
        ]
    )
    overrides = batch_resolve(["good plant", "bad", "another good plant"], {}, {})
    assert len(overrides) == 2
    assert {o.product_name_clean for o in overrides} == {"good plant", "another good plant"}


@patch("src.matching.llm._invoke_claude")
def test_concurrency_runs_batches_in_parallel(mock_invoke):
    """With concurrency>1 the in-flight `claude -p` calls overlap. Verify by
    asserting the wall-clock time is less than serial time."""
    n_batches = 4
    per_call_sleep = 0.2  # seconds — keep tiny so the test stays fast

    def slow_reply(prompt, *, model):
        time.sleep(per_call_sleep)
        products = json.loads(prompt.split("Products to match:\n", 1)[1])
        return json.dumps(
            [
                {
                    "product_name_clean": p,
                    "rhs_id": None,
                    "is_plant": False,
                    "product_category": "other",
                    "confidence": 0.5,
                    "reasoning": "",
                }
                for p in products
            ]
        )

    mock_invoke.side_effect = slow_reply

    # One product per batch
    names = [f"n_{b}_{i}" for b in range(n_batches) for i in range(BATCH_SIZE)]

    t0 = time.monotonic()
    overrides = batch_resolve(names, {}, {}, concurrency=4)
    parallel_s = time.monotonic() - t0

    assert len(overrides) == n_batches * BATCH_SIZE
    # 4 batches sleeping 0.2s each ~= 0.2s in parallel vs ~0.8s serial.
    # Allow generous slack for thread/process startup.
    assert parallel_s < per_call_sleep * n_batches * 0.75, (
        f"expected parallel speedup; ran in {parallel_s:.2f}s"
    )


@patch("src.matching.llm._invoke_claude")
def test_concurrency_callback_runs_on_main_thread(mock_invoke):
    """Persistence callback must always fire on the main thread so it doesn't
    need its own lock around the parquet rewrite."""
    main_thread = threading.get_ident()
    callback_threads: list[int] = []

    def reply(prompt, *, model):
        products = json.loads(prompt.split("Products to match:\n", 1)[1])
        return json.dumps(
            [
                {
                    "product_name_clean": p,
                    "rhs_id": None,
                    "is_plant": False,
                    "product_category": "other",
                    "confidence": 0.5,
                    "reasoning": "",
                }
                for p in products
            ]
        )

    mock_invoke.side_effect = reply

    def on_batch(_batch):
        callback_threads.append(threading.get_ident())

    names = [f"n_{b}_{i}" for b in range(3) for i in range(BATCH_SIZE)]
    batch_resolve(names, {}, {}, concurrency=3, on_batch_complete=on_batch)

    assert callback_threads, "callback never fired"
    assert all(t == main_thread for t in callback_threads), (
        f"callback ran off-thread: {callback_threads} vs main {main_thread}"
    )
