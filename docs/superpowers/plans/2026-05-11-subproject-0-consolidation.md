# Sub-project 0: Repo Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the scraping codebase into a `src/` layout with skeleton directories for the matching, transforms, and dashboard work in subsequent sub-projects. Pure refactor — zero behavioural change.

**Architecture:** Move `bronze/` → `src/scrapers/` and `cloud_storage/` → `src/common/` using `git mv` to preserve history; lock in current behaviour with import smoke tests written *before* the move (TDD); update the orchestrator's import paths; copy reference matching code from sister repo for sub-project 2 to replace; add empty stubs for `src/matching/`, `src/transforms/`, `site/`, `docs/research/`.

**Tech Stack:** Python 3.11+, pytest (added in this sub-project), git.

**Spec reference:** `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` §5.

---

## File structure

**Created in this sub-project:**

| Path | Responsibility |
|---|---|
| `src/__init__.py` | Top-level package marker |
| `src/scrapers/` (from `bronze/` via `git mv`) | All site-specific scrapers |
| `src/common/` (from `cloud_storage/` via `git mv`) | Shared utilities |
| `src/common/storage.py` (renamed from `cloud_storage.py`) | Parquet write + field defaults |
| `src/common/__init__.py` | Re-exports from `storage.py` |
| `src/matching/__init__.py` | Skeleton for sub-project 2 |
| `src/matching/legacy_match.py` | Reference copy of sister-repo matching code |
| `src/matching/legacy_combine_names.py` | Reference copy of sister-repo combine code |
| `src/transforms/__init__.py` | Skeleton for sub-project 2 |
| `site/.gitkeep` | Skeleton for sub-project 3 dashboard |
| `site/README.md` | One-line placeholder |
| `docs/research/.gitkeep` | Skeleton for sub-project R artefact |
| `tests/__init__.py` | Test root |
| `tests/smoke/__init__.py` | Smoke test package |
| `tests/smoke/test_imports.py` | Import smoke test (locks in behaviour) |
| `pyproject.toml` *(if missing — confirm in Task 1)* | pytest configuration |

**Modified in this sub-project:**

| Path | Change |
|---|---|
| `requirements.txt` | Add `pytest` |
| `load_bronze_data.py` | Update imports: `from bronze import …` → `from src.scrapers import …`; `import cloud_storage` → `from src.common.storage import export_data_locally` |
| `update_historic_files.py` | Update import: `import cloud_storage` → `from src.common import storage as cloud_storage` (kept aliased — minimal diff for a script we'll rewrite later) |

**Untouched in this sub-project:** `read_files.py`, `clear_invalid_files.py`, `clear_synonym.py`, `config/`, `data/`, `bronze/*.py` internals (the files move via `git mv` but their contents don't change), `cloud_storage/cloud_storage.py` internals.

---

## Task 1: Confirm test environment and add pytest

**Files:**
- Modify: `requirements.txt`
- Verify: `pyproject.toml` (create if missing — see step 2)

- [ ] **Step 1: Inspect current `requirements.txt`**

```bash
cat requirements.txt
```
Expected output (current state):
```
requests-html
selenium
bs4
polars==0.20.16
pyarrow
```

- [ ] **Step 2: Check whether `pyproject.toml` exists**

```bash
ls pyproject.toml
```
- If it exists, skip Step 3.
- If it does not exist (most likely), continue to Step 3.

- [ ] **Step 3: Create a minimal `pyproject.toml` for pytest discovery**

Write `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 4: Add pytest and lxml_html_clean to requirements**

Edit `requirements.txt` to add two new lines:
```
requests-html
selenium
bs4
polars==0.20.16
pyarrow
pytest
lxml_html_clean
```

The `lxml_html_clean` package is a discovered transitive dependency: `requests-html` (unmaintained) imports `from lxml.html.clean import Cleaner`, which `lxml >= 5` no longer ships in-package. Without `lxml_html_clean` (or pinning `lxml<5`), every scraper that imports `requests-html` will fail at import time. We add `lxml_html_clean` rather than pinning `lxml<5` because the latter is the upstream-recommended path; both `requests-html` and `requests-html`'s direct usage of `lxml` will be removed entirely in sub-project 1 (`httpx` + `playwright`).

- [ ] **Step 5: Install pytest into the active venv**

```bash
pip install pytest
```
Expected: pytest installs successfully.

- [ ] **Step 6: Verify pytest discovers an empty test suite**

```bash
pytest -q
```
Expected: `no tests ran in 0.0Xs` (we have no tests yet — that's correct).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pyproject.toml
git commit -m "$(cat <<'EOF'
add pytest dependency for repo consolidation work

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Write smoke test that locks in CURRENT import paths

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/smoke/__init__.py`
- Create: `tests/smoke/test_imports.py`

This task captures today's behaviour as a regression baseline before we move anything. The test must pass against the current code.

- [ ] **Step 1: Create empty `__init__.py` files**

Write `tests/__init__.py` (empty file).
Write `tests/smoke/__init__.py` (empty file).

- [ ] **Step 2: Write the smoke test for current paths**

Write `tests/smoke/test_imports.py`. We use `importlib.import_module()` rather than binding `from … import name` so static analysers don't flag unused imports (`# noqa: F401` only silences ruff/flake8, not Pyright) and so the test expresses its intent cleanly: "load this module by dotted name and don't crash". On failure, `importlib` reports the offending module name precisely.

```python
"""Import smoke test.

Locks in the current module layout so the consolidation refactor (sub-project 0)
cannot accidentally break the orchestrator's imports. After the refactor, the
"current path" tests below are removed and replaced with "new path" tests in
later tasks of this same sub-project.
"""

import importlib


def test_bronze_scrapers_importable():
    for name in (
        "bronze.arboretum",
        "bronze.carragh",
        "bronze.common",
        "bronze.gardens4you",
        "bronze.quickcrop",
        "bronze.rhs",
        "bronze.rhs_urls",
        "bronze.tullys",
    ):
        importlib.import_module(name)


def test_cloud_storage_importable():
    cloud_storage = importlib.import_module("cloud_storage")

    assert hasattr(cloud_storage, "export_data_locally")
    assert hasattr(cloud_storage, "add_defaults_to_fields")


def test_orchestrator_importable():
    importlib.import_module("load_bronze_data")
```

- [ ] **Step 3: Run the smoke test to verify it passes**

```bash
pytest tests/smoke/test_imports.py -v
```
Expected: `3 passed`. If any fail, STOP — the move-related work below assumes a clean baseline.

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "$(cat <<'EOF'
add import smoke test as baseline for consolidation refactor

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create `src/` package skeleton

**Files:**
- Create: `src/__init__.py`

Tiny preparatory step. We make `src/` a package now so subsequent `git mv` operations land inside an existing tree.

- [ ] **Step 1: Create the directory and init file**

```bash
mkdir -p src
```
Write `src/__init__.py` (empty file).

- [ ] **Step 2: Verify smoke tests still pass**

```bash
pytest tests/smoke/test_imports.py -v
```
Expected: `3 passed`. (Adding an empty package shouldn't affect anything.)

- [ ] **Step 3: Commit**

```bash
git add src/__init__.py
git commit -m "$(cat <<'EOF'
add src/ package skeleton for consolidation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Move `bronze/` → `src/scrapers/` and update orchestrator

**Files:**
- Move: `bronze/` → `src/scrapers/`
- Modify: `load_bronze_data.py` (line 5)
- Modify: `tests/smoke/test_imports.py` (replace `from bronze import …` test)

- [ ] **Step 1: Move the directory preserving git history**

```bash
git mv bronze src/scrapers
```

- [ ] **Step 2: Verify the move**

```bash
ls src/scrapers/
```
Expected output (8 files, plus `__init__.py`):
```
__init__.py  arboretum.py  carragh.py  common.py  gardens4you.py  quickcrop.py  rhs.py  rhs_urls.py  tullys.py
```

- [ ] **Step 3: Update the orchestrator import**

Edit `load_bronze_data.py` line 5.

Old:
```python
from bronze import tullys, quickcrop, gardens4you, carragh, arboretum, rhs_urls, rhs
```

New:
```python
from src.scrapers import tullys, quickcrop, gardens4you, carragh, arboretum, rhs_urls, rhs
```

- [ ] **Step 4: Update the smoke test for the new path**

Edit `tests/smoke/test_imports.py`. Replace the `test_bronze_scrapers_importable` function with:
```python
def test_scrapers_importable():
    for name in (
        "src.scrapers.arboretum",
        "src.scrapers.carragh",
        "src.scrapers.common",
        "src.scrapers.gardens4you",
        "src.scrapers.quickcrop",
        "src.scrapers.rhs",
        "src.scrapers.rhs_urls",
        "src.scrapers.tullys",
    ):
        importlib.import_module(name)
```

Leave `test_cloud_storage_importable` and `test_orchestrator_importable` alone — they get updated in Task 5.

- [ ] **Step 5: Run the smoke test**

```bash
pytest tests/smoke/test_imports.py -v
```
Expected: all 3 tests pass. If `test_orchestrator_importable` fails with `ModuleNotFoundError: No module named 'bronze'`, the orchestrator update in Step 3 was missed — fix and re-run.

- [ ] **Step 6: Commit**

`git mv` already stages the renames, so we only need to add the file modifications:

```bash
git add load_bronze_data.py tests/smoke/test_imports.py
git commit -m "$(cat <<'EOF'
move bronze/ to src/scrapers/ and update orchestrator imports

Pure refactor — git mv preserves history. Smoke test updated to
match new import path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Move `cloud_storage/` → `src/common/` and rename file

**Files:**
- Move: `cloud_storage/` → `src/common/`
- Rename: `src/common/cloud_storage.py` → `src/common/storage.py`
- Modify: `src/common/__init__.py` (`from .cloud_storage import *` → `from .storage import *`)
- Modify: `load_bronze_data.py` (line 4 + every call site of `cloud_storage.export_data_locally`)
- Modify: `update_historic_files.py` (line 5 import)
- Modify: `tests/smoke/test_imports.py` (replace `import cloud_storage` test)

- [ ] **Step 1: Move the package directory**

```bash
git mv cloud_storage src/common
```

- [ ] **Step 2: Rename the inner module**

```bash
git mv src/common/cloud_storage.py src/common/storage.py
```

- [ ] **Step 3: Update `src/common/__init__.py`**

Replace the file's single line:

Old:
```python
from .cloud_storage import *
```

New:
```python
from .storage import *
```

- [ ] **Step 4: Update `load_bronze_data.py` import**

Edit line 4.

Old:
```python
import cloud_storage
```

New:
```python
from src.common.storage import export_data_locally
```

- [ ] **Step 5: Update every call site in `load_bronze_data.py`**

Replace all `cloud_storage.export_data_locally(...)` with `export_data_locally(...)`.

The orchestrator currently calls `cloud_storage.export_data_locally` 11 times (lines 13, 17, 21, 25, 29, 33, 44, 47, 48, 49, 50 — verify with `grep -n cloud_storage load_bronze_data.py` after Step 4). Use a single replace-all on the file: drop the `cloud_storage.` prefix.

After this step, `grep -n cloud_storage load_bronze_data.py` should return no matches.

- [ ] **Step 6: Update `update_historic_files.py` import**

Edit line 5.

Old:
```python
import cloud_storage
```

New:
```python
from src.common import storage as cloud_storage
```

(Keeping the local alias `cloud_storage` because line 21's `cloud_storage.add_defaults_to_fields(...)` then needs no further change. This script gets rewritten properly in a later sub-project.)

- [ ] **Step 7: Update the smoke test**

Edit `tests/smoke/test_imports.py`. Replace `test_cloud_storage_importable` with:
```python
def test_storage_importable():
    storage = importlib.import_module("src.common.storage")

    assert callable(storage.export_data_locally)
    assert callable(storage.add_defaults_to_fields)


def test_storage_package_reexports():
    common = importlib.import_module("src.common")

    assert callable(common.export_data_locally)
    assert callable(common.add_defaults_to_fields)
```

- [ ] **Step 8: Run the smoke test**

```bash
pytest tests/smoke/test_imports.py -v
```
Expected: 4 tests pass (`test_scrapers_importable`, `test_storage_importable`, `test_storage_package_reexports`, `test_orchestrator_importable`).

- [ ] **Step 9: Sanity-check the orchestrator parses without scraping**

```bash
python load_bronze_data.py --help
```
Expected: argparse usage prints, exit 0. (This proves all imports resolve. We do NOT run an actual scrape — that's a manual verification step at the end of this plan.)

- [ ] **Step 10: Commit**

`git mv` already stages the moves and rename, so we only need to add the file modifications:

```bash
git add src/common/__init__.py load_bronze_data.py update_historic_files.py tests/smoke/test_imports.py
git commit -m "$(cat <<'EOF'
move cloud_storage/ to src/common/ and rename to storage.py

Updates orchestrator and update_historic_files.py call sites; smoke
test now covers both direct module import and package re-export path.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add skeleton directories for sub-projects 2, 3, R

**Files:**
- Create: `src/matching/__init__.py`
- Create: `src/transforms/__init__.py`
- Create: `site/.gitkeep`
- Create: `site/README.md`
- Create: `docs/research/.gitkeep` *(only if sub-project R hasn't already populated this directory by the time you reach this task)*

- [ ] **Step 1: Create the matching/transforms skeletons**

```bash
mkdir -p src/matching src/transforms
```
Write `src/matching/__init__.py` (empty file).
Write `src/transforms/__init__.py` (empty file).

- [ ] **Step 2: Create the dashboard skeleton**

```bash
mkdir -p site
```
Write `site/.gitkeep` (empty file).
Write `site/README.md`:
```markdown
# Dashboard

Observable Framework site — populated in sub-project 3
(see `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` §8).
```

- [ ] **Step 3: Ensure `docs/research/` exists**

```bash
ls docs/research/
```
- If the directory already contains `nurseries-ireland-shipping.md` (populated by sub-project R), skip the `.gitkeep` step.
- If the directory does not exist, create it and add `.gitkeep`:
  ```bash
  mkdir -p docs/research
  ```
  Write `docs/research/.gitkeep` (empty file).

- [ ] **Step 4: Verify smoke tests still pass**

```bash
pytest tests/smoke/test_imports.py -v
```
Expected: 4 tests pass. (No imports affected, but a sanity check is cheap.)

- [ ] **Step 5: Commit**

```bash
git add src/matching/ src/transforms/ site/ docs/research/
git commit -m "$(cat <<'EOF'
add skeleton directories for matching, transforms, dashboard

Empty stubs for sub-projects 2 (matching/transforms) and 3 (dashboard);
docs/research/ skeleton aligned with sub-project R.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Copy reference matching code from sister repo

**Files:**
- Create: `src/matching/legacy_match.py`
- Create: `src/matching/legacy_combine_names.py`

Sub-project 2 will replace these. They live in this repo as a reference so the matching rewrite has the prior implementation in front of it without round-tripping to a separate repo.

- [ ] **Step 1: Read the sister-repo source files**

Source paths (in the sister repo):
- `C:\Users\andre\OneDrive\Documents\Development\blaithin\docker\blaithin\transformers\match_product_to_plant.py`
- `C:\Users\andre\OneDrive\Documents\Development\blaithin\docker\blaithin\transformers\combine_common_and_botanical_names.py`

Read both files.

- [ ] **Step 2: Write `src/matching/legacy_match.py`**

Copy the body of `match_product_to_plant.py` into `src/matching/legacy_match.py` with this header prepended (keep the original docstring/code below the header, including the Mage AI `@transformer` and `@test` decorators — they won't run here but they're informative for the reader):

```python
"""Reference: legacy plant-to-product matcher from the Mage AI pipeline.

Source: blaithin/docker/blaithin/transformers/match_product_to_plant.py
(sister repo as of 2026-05-11)

This file exists as a documentation reference for sub-project 2 (matching v2),
which will REPLACE this approach with:
  - gnparser for botanical name parsing
  - exact (genus, species) lookup against RHS
  - rapidfuzz residual on synonyms + common names
  - LLM batch fallback for the long tail
  - cultivar preserved as a first-class column on the product row

DO NOT IMPORT from this module. It will be deleted at the end of sub-project 2.
"""

# ---- ORIGINAL CONTENT BELOW ----

<paste original file content here, including the Mage decorators>
```

- [ ] **Step 3: Write `src/matching/legacy_combine_names.py`**

Same pattern — copy `combine_common_and_botanical_names.py` with the analogous reference header:

```python
"""Reference: legacy "combine RHS botanical and common names" transformer.

Source: blaithin/docker/blaithin/transformers/combine_common_and_botanical_names.py
(sister repo as of 2026-05-11)

This file exists as a documentation reference for sub-project 2 (matching v2).
The REPLACEMENT keeps RHS records as one row per (genus, species) with a
synonyms[] field, instead of flattening botanical and common names into a
single deduped column. See spec §6.1 for the new schema.

DO NOT IMPORT from this module. It will be deleted at the end of sub-project 2.
"""

# ---- ORIGINAL CONTENT BELOW ----

<paste original file content here>
```

- [ ] **Step 4: Verify smoke tests still pass**

```bash
pytest tests/smoke/test_imports.py -v
```
Expected: 4 tests pass. (We didn't touch any production code.)

- [ ] **Step 5: Commit**

```bash
git add src/matching/legacy_match.py src/matching/legacy_combine_names.py
git commit -m "$(cat <<'EOF'
add reference legacy matching code from sister repo

Copied verbatim from blaithin/docker/blaithin/transformers/. Marked
as reference-only with prominent docstring; will be deleted at the
end of sub-project 2 once gnparser+LLM-fallback matcher lands.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Manual end-to-end verification

This task is deliberately not a pytest test — actually scraping a live nursery is slow and flaky for CI. The maintainer (or the executing agent) should run this once at the end of sub-project 0 to confirm nothing regressed.

- [ ] **Step 1: Run a real Tully's scrape (smallest, simplest scraper, no Selenium)**

```bash
python load_bronze_data.py --site tullys
```
Expected:
- Some `Storing data to file 'data\tullys\YYYY-MM-DD.parquet'` output.
- A new (or overwritten) `data/tullys/YYYY-MM-DD.parquet` file appears.
- Process exits with code 0.

- [ ] **Step 2: Verify the parquet is non-empty and structurally identical to a recent prior run**

```bash
python -c "import polars as pl; df = pl.read_parquet('data/tullys/$(date +%Y-%m-%d).parquet'); print(df.shape); print(df.columns)"
```
Expected: a row count in the same order of magnitude as recent dated parquets in `data/tullys/`, with the same columns.

- [ ] **Step 3: If verification passed, no commit needed for this task — sub-project 0 is complete.**

If verification failed, do NOT proceed to sub-project 2. Investigate and fix:
- `ModuleNotFoundError` → an import path was missed in Task 4 or 5; re-grep for `bronze` / `cloud_storage` in `load_bronze_data.py`.
- Other errors → likely unrelated to this refactor (a scraper was broken before too); confirm by checking out the pre-refactor commit and re-running.

---

## Out of scope for sub-project 0

These are intentionally deferred to later sub-projects — do NOT include them in this plan's work, even if you notice them:

- Hardcoded Windows path separators in `src/common/storage.py` (`data\\{source}\\…`) — sub-project 1 hardening replaces with `pathlib`.
- Hardcoded fallback values like `size = "9 cm"` in scrapers — sub-project 1.
- Driver/session resource leaks — sub-project 1.
- Replacing `requests-html` (unmaintained) — sub-project 1.
- Replacing the legacy matching code with gnparser + LLM fallback — sub-project 2.
- Sister-repo cleanup (`MIGRATED.md`, deletion of Terraform/dbt/Mage/docker) — handled at the end of sub-project 2 once we've verified the matching port works.
- New nursery scrapers (Farmer Gracy, Bulbi, GreenGardenFlowerBulbs, plus selections from sub-project R research) — sub-project 1.
- Dashboard implementation — sub-project 3.
- CI workflows, VCR fixtures, snapshot diff alerts — sub-project 4.

---

## Self-review checklist (run before declaring sub-project 0 done)

- [ ] All 8 tasks above show every step ticked.
- [ ] `pytest tests/smoke/test_imports.py -v` shows 4 passing tests.
- [ ] `python load_bronze_data.py --help` exits 0.
- [ ] Manual Task 8 scrape succeeded with a fresh dated parquet.
- [ ] `git log --oneline` shows ~7 commits with `git mv` history preserved (`git log --follow src/scrapers/tullys.py` should show pre-move commits).
- [ ] No file at the repo root references `bronze.` or `cloud_storage.` (verify: `grep -RIn "from bronze\|import cloud_storage\|cloud_storage\." --exclude-dir=src --exclude-dir=docs --exclude-dir=.git .` should return empty).
- [ ] `bronze/` and `cloud_storage/` directories no longer exist at the repo root.
