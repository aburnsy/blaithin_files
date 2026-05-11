# Sub-project 4: CI/CD + Observability Implementation Plan

> Use superpowers:subagent-driven-development. Checkbox `- [ ]` syntax.

**Goal:** GitHub Actions for PR validation + nightly scrape + dashboard deploy. Plus a small `bug_alerts.md` page tying scrape report alerts into the health view.

**Tech:** GitHub Actions YAML, Node 20, Python 3.11.

**Spec reference:** `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` §9.

---

## File structure

| Path | Responsibility |
|---|---|
| `.github/workflows/ci.yml` | On PR: lint (ruff) + pytest + dashboard build |
| `.github/workflows/scrape.yml` | Nightly cron: run scrapers + matching, commit data, deploy |
| `.github/workflows/deploy.yml` | On push to main: build site/dist/ + deploy to GitHub Pages |
| `pyproject.toml` | Add `[tool.ruff]` config |
| `requirements-dev.txt` | New: `ruff` (separated from prod deps for cleanliness) |
| `README.md` | Replace with project summary + dashboard link |

---

## Tasks

### Task 1: requirements-dev.txt + ruff config

- [ ] Create `requirements-dev.txt`:
  ```
  -r requirements.txt
  ruff
  ```

- [ ] Add to `pyproject.toml`:
  ```toml
  [tool.ruff]
  line-length = 100
  target-version = "py311"

  [tool.ruff.lint]
  select = ["E", "F", "I", "B", "UP"]
  ignore = ["E501"]  # line length handled by formatter

  [tool.ruff.lint.per-file-ignores]
  "tests/**" = ["B"]
  ```

- [ ] Run `pip install ruff` then `ruff check .` from repo root. Fix any trivial issues. Don't fix anything in `legacy_*.py` (they're deleted now anyway) or `bronze/cloud_storage` (gone).

- [ ] Commit:
  ```
  add ruff config + requirements-dev.txt
  ```

### Task 2: CI workflow

- [ ] Create `.github/workflows/ci.yml`:
  ```yaml
  name: CI
  on:
    pull_request:
    push:
      branches: [main]
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: "3.11" }
        - run: pip install -r requirements-dev.txt
        - run: ruff check .
        - run: pytest -v
    build-site:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with: { node-version: "20" }
        - run: cd site && npm ci
        - run: cd site && npm run build
  ```

- [ ] Commit:
  ```
  add CI workflow: ruff + pytest + dashboard build
  ```

### Task 3: Nightly scrape workflow

- [ ] Create `.github/workflows/scrape.yml`:
  ```yaml
  name: Nightly scrape
  on:
    schedule:
      - cron: "0 4 * * *"  # 04:00 UTC daily
    workflow_dispatch:
  jobs:
    scrape:
      runs-on: ubuntu-latest
      strategy:
        matrix:
          site: [tullys, arboretum, carragh, gardens4you, quickcrop, hedgingie, david_austin]
        fail-fast: false
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: "3.11" }
        - run: pip install -r requirements.txt
        - run: python load_bronze_data.py --site ${{ matrix.site }} || true
        - uses: actions/upload-artifact@v4
          with:
            name: ${{ matrix.site }}
            path: data/${{ matrix.site }}/
    match-and-commit:
      needs: scrape
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: "3.11" }
        - run: pip install -r requirements.txt
        - uses: actions/download-artifact@v4
          with: { path: data }
        - run: python load_bronze_data.py --matching --no-llm
        - name: Commit data
          run: |
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add data/
            git diff --cached --quiet || git commit -m "nightly scrape $(date -u +%Y-%m-%d)"
            git push
  ```

- [ ] Commit:
  ```
  add nightly scrape workflow with parallel matrix per site
  ```

### Task 4: Deploy workflow

- [ ] Create `.github/workflows/deploy.yml`:
  ```yaml
  name: Deploy site
  on:
    push:
      branches: [main]
      paths: [site/**, data/**]
    workflow_dispatch:
  permissions:
    pages: write
    id-token: write
  jobs:
    deploy:
      runs-on: ubuntu-latest
      environment:
        name: github-pages
        url: ${{ steps.deployment.outputs.page_url }}
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with: { node-version: "20" }
        - run: cd site && npm ci
        - run: cd site && npm run build
        - uses: actions/configure-pages@v4
        - uses: actions/upload-pages-artifact@v3
          with: { path: site/dist }
        - id: deployment
          uses: actions/deploy-pages@v4
  ```

- [ ] Commit:
  ```
  add GitHub Pages deploy workflow
  ```

### Task 5: README

- [ ] Replace repo-root `README.md`:
  ```markdown
  # blaithin_files

  Plant price comparison across Irish, UK, and EU online nurseries.

  ## What this is

  Daily scrapes of nursery websites → matched to RHS plant database →
  served as a static dashboard. All free, all open.

  - **Dashboard:** https://aburnsy.github.io/blaithin_files/ (GitHub Pages)
  - **Spec:** `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md`
  - **Plans:** `docs/superpowers/plans/`
  - **Nursery research:** `docs/research/nurseries-ireland-shipping.md`

  ## Run locally

  ```
  python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
  pip install -r requirements.txt
  python load_bronze_data.py --site tullys     # scrape one site
  python load_bronze_data.py --matching        # run matching pipeline
  cd site && npm install && npm run dev        # run dashboard locally
  ```

  ## Layout

  - `src/scrapers/` — site-specific scrapers, all on `BaseScraper`
  - `src/matching/` — gnparser+rapidfuzz+LLM-fallback pipeline
  - `src/common/` — storage, logging, FX, nursery config loader
  - `site/` — Observable Framework dashboard
  - `data/` — parquet snapshots (committed; refreshed by nightly cron)
  - `config/` — per-nursery URL lists + `nurseries.yaml` metadata
  - `tests/` — pytest suite + VCR fixtures
  ```

- [ ] Commit:
  ```
  rewrite README with project summary + dashboard link
  ```

### Task 6: Run pytest one final time on main, smoke verify

- [ ] `pytest -v` — expect all pass
- [ ] `cd site && npm run build` — expect clean
- [ ] No commit

---

## Out of scope

- Self-hosted runner setup (runs_on=self-hosted nurseries — that's a one-time per-user op)
- LLM key management (ANTHROPIC_API_KEY would be a GitHub secret; optional)
- Email/Slack alerts on scrape failures
