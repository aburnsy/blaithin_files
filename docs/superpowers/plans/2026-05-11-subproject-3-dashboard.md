# Sub-project 3: Dashboard (Observable Framework) Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement task-by-task. Checkbox `- [ ]` syntax for tracking.

**Goal:** A static-site plant comparison dashboard at `site/`, served from `data/products_matched.parquet` + `data/rhs.parquet` + `data/nurseries.parquet` via DuckDB-WASM in the browser. Drill-down filters, sortable tables, embedded links to RHS pages and nursery product URLs, separate non-plant view.

**Architecture:** Observable Framework (Markdown + JS), DuckDB-WASM for SQL filtering in-browser, parquet bundles built into the static output. Build with `npm run build` in `site/`, deploy artefact is plain HTML/JS suitable for GitHub Pages.

**Tech Stack:** Node.js 20+, Observable Framework 1.x, DuckDB-WASM (loaded via Observable's built-in support).

**Spec reference:** `docs/superpowers/specs/2026-05-11-blaithin-redesign-design.md` §8.

---

## Phases

| Phase | Tasks | Output |
|---|---|---|
| **A. Scaffold** | 1–2 | Observable Framework initialised in `site/`; data files wired in |
| **B. Pages** | 3–6 | Plant search, cultivar detail, non-plant view, nursery overview |
| **C. Polish** | 7–8 | Health page (scraper status), build smoke |

Total: ~8 tasks, ~3-5 days.

---

## File structure

**Created in `site/`:**

| Path | Responsibility |
|---|---|
| `site/package.json` | Observable Framework deps + scripts |
| `site/observablehq.config.js` | Site config (title, deps, output dir) |
| `site/index.md` | Landing page → links to the 4 main views |
| `site/plants.md` | Primary plant search with drill-down filters |
| `site/cultivar.md` | Per-cultivar nursery price comparison |
| `site/non-plants.md` | Compost/tools/pots/fertilisers comparison |
| `site/nurseries.md` | Per-nursery overview |
| `site/health.md` | Scrape report visualisation |
| `site/data/products.parquet.js` | Data loader — copies/transforms from repo's data/ |
| `site/data/rhs.parquet.js` | Data loader for RHS metadata |
| `site/data/nurseries.json.js` | Data loader for nursery config (currency, delivery, etc.) |
| `site/components/filters.js` | Reusable filter sidebar component |
| `site/components/product_table.js` | Reusable sortable product table |
| `site/.gitignore` | Ignore node_modules, dist, cache |

**Modified at repo root:**

| Path | Change |
|---|---|
| `.gitignore` | Add `site/node_modules`, `site/dist`, `site/.observablehq` |

---

## Phase A — Scaffold

### Task 1: Initialize Observable Framework in `site/`

- [ ] **Step 1: Verify Node.js available**

```
node --version
npm --version
```
Expect: Node 20+ and npm. If missing, STOP and report — user needs to install Node before this sub-project.

- [ ] **Step 2: Initialize Observable Framework**

```
cd site
npx --yes @observablehq/framework@latest init . --no-install
cd ..
```

This creates `site/observablehq.config.js`, `site/package.json`, `site/src/index.md`, etc. The `--no-install` skips npm install for now (we batch in Step 3).

If `npx init` rejects the existing dir (because `site/README.md` exists from sub-project 0), move it temporarily, init, then move it back.

- [ ] **Step 3: Install dependencies**

```
cd site
npm install
cd ..
```

Expect: deps install (~50-100MB in `site/node_modules`).

- [ ] **Step 4: Verify the dev server starts**

```
cd site
npm run dev &
DEV_PID=$!
sleep 8
curl -s http://localhost:3000/ | head -20
kill $DEV_PID
cd ..
```

Expect: HTML output on stdout. If the server fails to start, report.

- [ ] **Step 5: Add `.gitignore` entries**

Append to repo-root `.gitignore` (create if missing):
```
site/node_modules/
site/dist/
site/.observablehq/
```

- [ ] **Step 6: Commit**

```
git add site/ .gitignore
git commit -m "$(cat <<'EOF'
scaffold Observable Framework site/

Bare init with default landing page. Subsequent tasks add data loaders,
filter components, and the plant/cultivar/non-plant/nursery/health pages.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Data loaders (parquets + nursery config → site/data/)

- [ ] **Step 1: Write `site/src/data/products.parquet.js`**

Observable Framework data loaders run at build time. Output file extension determines format. We copy the repo's `data/products_matched.parquet` into the site's data dir — Observable serves it as a static asset, accessible via `FileAttachment("data/products.parquet")` in pages.

Content:
```javascript
// site/src/data/products.parquet.js
import {createReadStream} from "node:fs";
import {pipeline} from "node:stream/promises";

await pipeline(
  createReadStream("../data/products_matched.parquet"),
  process.stdout,
);
```

- [ ] **Step 2: Write `site/src/data/rhs.parquet.js`**

Same pattern, copying `../data/rhs.parquet`.

- [ ] **Step 3: Write `site/src/data/nurseries.json.js`**

Loads `config/nurseries.yaml` and emits as JSON (Observable's pages can `import` JSON natively).

```javascript
// site/src/data/nurseries.json.js
import {readFile} from "node:fs/promises";
import {parse} from "yaml";

const yaml = await readFile("../config/nurseries.yaml", "utf8");
const data = parse(yaml);
process.stdout.write(JSON.stringify(data, null, 2));
```

Add `yaml` to site's package.json: `npm install yaml --save`.

- [ ] **Step 4: Verify the loaders run during build**

```
cd site
npm run build
ls dist/data/
```

Expect: `dist/data/products.parquet`, `dist/data/rhs.parquet`, `dist/data/nurseries.json` all present.

- [ ] **Step 5: Commit**

```
git add site/src/data/ site/package.json site/package-lock.json
git commit -m "$(cat <<'EOF'
add Observable data loaders for parquets + nursery config

products.parquet.js / rhs.parquet.js stream the repo's parquets into
the site's data directory; nurseries.json.js parses the YAML into JSON.
All run at `npm run build` time and produce static assets the pages
load via FileAttachment.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase B — Pages

### Task 3: Plant search page (`site/src/plants.md`)

The primary view. Filter sidebar (sun, soil, hardiness, height, foliage, in-stock, plant_type, cultivar text), result table (one row per cultivar/species, all nursery prices), sort by any column, link out to RHS + nursery URLs.

- [ ] **Step 1: Write `site/src/plants.md`**

Content (Observable Markdown + JS chunks):
```markdown
---
title: Plants — search & compare
---

# Plants

Filter by growing conditions, sort by any column, click through to RHS or the nursery's product page.

```js
const products = FileAttachment("data/products.parquet").parquet();
const rhs = FileAttachment("data/rhs.parquet").parquet();
```

```js
const products_db = await DuckDBClient.of({products, rhs});
```

```js
// Filter inputs
const sun = view(Inputs.checkbox(["Full sun", "Partial shade", "Full shade"], {label: "Sun"}));
const hardiness = view(Inputs.range([1, 10], {label: "Min hardiness (H)", value: 1}));
const inStock = view(Inputs.toggle({label: "In stock only", value: false}));
```

```js
const filtered = await products_db.query(`
  SELECT
    p.genus,
    p.species,
    p.cultivar,
    p.product_name_raw,
    p.source AS nursery,
    p.price_native,
    p.currency,
    p.size,
    p.stock,
    p.product_url,
    r.rhs_id,
    r.common_names,
    r.plant_url AS rhs_url,
    r.hardiness,
    r.sun_exposure
  FROM products p
  LEFT JOIN rhs r USING (rhs_id)
  WHERE p.is_plant = true
    AND p.rhs_id IS NOT NULL
    ${inStock ? "AND p.stock IS NOT NULL AND p.stock > 0" : ""}
  ORDER BY p.genus, p.species, p.price_native
`);
```

```js
Inputs.table(filtered, {
  columns: ["genus", "species", "cultivar", "nursery", "price_native", "currency", "size", "stock", "rhs_url", "product_url"],
  format: {
    rhs_url: x => x ? html`<a href="${x}" target="_blank">RHS</a>` : "—",
    product_url: x => x ? html`<a href="${x}" target="_blank">Buy</a>` : "—",
    price_native: x => x?.toFixed(2),
  },
})
```
```

(That's a lot of JS in markdown — Observable's syntax. Test by running `npm run dev` and viewing http://localhost:3000/plants.)

- [ ] **Step 2: Run dev server and visually verify**

```
cd site
npm run dev
```

Open http://localhost:3000/plants in a browser. Confirm:
- Filter sidebar renders with sun checkboxes, hardiness range, in-stock toggle
- Table renders with rows
- Clicking RHS link opens RHS page in new tab
- Clicking Buy link opens nursery product page in new tab

Stop the dev server when done.

- [ ] **Step 3: Commit**

```
git add site/src/plants.md
git commit -m "$(cat <<'EOF'
add plant search page with filters and sortable comparison table

Sidebar filters (sun, hardiness, in-stock); SQL-backed result table
joining products → RHS metadata; per-row links out to RHS and nursery
product pages. DuckDB-WASM does the filter math client-side.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Cultivar detail page (`site/src/cultivar.md`)

Per-cultivar nursery price comparison — one row per nursery, all the buying details (price native + EUR, size, stock, delivery fee, min order, VAT note, total-to-door estimate).

- [ ] **Step 1: Write `site/src/cultivar.md`**

```markdown
---
title: Cultivar detail
---

```js
import nurseries from "./data/nurseries.json";

const products = FileAttachment("data/products.parquet").parquet();
const rhs = FileAttachment("data/rhs.parquet").parquet();
const products_db = await DuckDBClient.of({products, rhs});
```

```js
// Pick a cultivar by URL hash (e.g. /cultivar#Acer-palmatum-Bloodgood) or default
const params = new URLSearchParams(location.search);
const genus = view(Inputs.text({label: "Genus", value: params.get("genus") || "Acer"}));
const species = view(Inputs.text({label: "Species", value: params.get("species") || "palmatum"}));
const cultivar = view(Inputs.text({label: "Cultivar (optional)", value: params.get("cultivar") || ""}));
```

```js
const matches = await products_db.query(`
  SELECT
    p.source AS nursery,
    p.product_name_raw,
    p.price_native,
    p.currency,
    p.price_eur,
    p.size,
    p.stock,
    p.product_url
  FROM products p
  WHERE p.genus = $1 AND p.species = $2
    ${cultivar ? "AND p.cultivar = $3" : ""}
  ORDER BY COALESCE(p.price_eur, p.price_native)
`, cultivar ? [genus, species, cultivar] : [genus, species]);
```

```js
const enriched = matches.toArray().map(row => {
  const cfg = nurseries[row.nursery] || {};
  const flatFee = (cfg.delivery_fees && cfg.delivery_fees[0]?.fee_eur) || 0;
  const totalToDoor = (row.price_eur || row.price_native || 0) + flatFee;
  return {
    ...row,
    delivery_eur: flatFee,
    min_order: cfg.min_order_eur || 0,
    vat_note: cfg.vat_included ? "" : "VAT may apply at customs",
    total_to_door_eur: totalToDoor,
  };
});
```

```js
Inputs.table(enriched, {
  columns: ["nursery", "product_name_raw", "price_native", "currency", "price_eur", "size", "stock", "delivery_eur", "min_order", "vat_note", "total_to_door_eur", "product_url"],
  format: {
    product_url: x => x ? html`<a href="${x}" target="_blank">Buy</a>` : "—",
    price_native: x => x?.toFixed(2),
    price_eur: x => x?.toFixed(2),
    total_to_door_eur: x => x?.toFixed(2),
    delivery_eur: x => x?.toFixed(2),
  },
})
```
```

- [ ] **Step 2: Verify in dev server, commit**

```
git add site/src/cultivar.md
git commit -m "$(cat <<'EOF'
add cultivar detail page: one row per nursery with delivery + VAT

Total-to-door estimate combines price_eur + flat delivery fee from
nurseries.json config. Plain text fields for genus/species/cultivar
let users link to a specific plant via query string (e.g. ?genus=Acer&species=palmatum).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Non-plant comparison page (`site/src/non-plants.md`)

Same drill-down + sortable pattern but filtered to `is_plant = false`. Categories: compost, soil, tool, pot, fertiliser, accessory.

- [ ] **Step 1: Write `site/src/non-plants.md`** following the plants.md pattern but with `WHERE is_plant = false` and a category filter instead of plant-specific filters.

- [ ] **Step 2: Verify + commit**

---

### Task 6: Nursery overview page (`site/src/nurseries.md`)

One row per nursery: display name, base URL, currency, delivery type, min order, VAT note, last-scraped date, product count, plant vs non-plant split.

- [ ] **Step 1: Write `site/src/nurseries.md`** — read nurseries.json, JOIN to product counts grouped by source.

- [ ] **Step 2: Verify + commit**

---

## Phase C — Polish

### Task 7: Health page (`site/src/health.md`)

Visualisation of `data/scrape_reports.parquet` (or the latest reports/<date>.jsonl) — per-site row counts over time, error counts, last-successful-run timestamp.

For v1: simple line chart per nursery showing products_parsed over time.

- [ ] **Step 1: Add a data loader for the JSONL reports** at `site/src/data/reports.json.js`:
```javascript
import {readFile, readdir} from "node:fs/promises";
import path from "node:path";

const REPORTS_DIR = "../reports";
const all = [];
try {
  const files = await readdir(REPORTS_DIR);
  for (const f of files.filter(x => x.endsWith(".jsonl"))) {
    const content = await readFile(path.join(REPORTS_DIR, f), "utf8");
    for (const line of content.trim().split("\n").filter(Boolean)) {
      all.push(JSON.parse(line));
    }
  }
} catch {
  // No reports yet — first run
}
process.stdout.write(JSON.stringify(all, null, 2));
```

- [ ] **Step 2: Write `site/src/health.md`** with a Plot line chart (Observable's Plot library is built in).

- [ ] **Step 3: Commit**

---

### Task 8: Build + smoke

- [ ] **Step 1: Run a clean build**

```
cd site
rm -rf dist .observablehq/cache
npm run build
ls dist/
```

Expect: `dist/index.html`, `dist/plants/index.html`, `dist/cultivar/index.html`, etc., plus `dist/_file/` containing the parquets.

- [ ] **Step 2: Serve `dist/` and visually click through every page**

```
cd site
npx --yes serve dist -p 4000 &
SERVE_PID=$!
sleep 5
curl -s http://localhost:4000/plants/ | head -10
kill $SERVE_PID
cd ..
```

Open the served URL in a browser, click through each page, confirm each renders without console errors.

- [ ] **Step 3: Commit any final fixes**

```bash
git add -A
git commit -m "$(cat <<'EOF'
finalise dashboard build; all 4 main pages render against production data

Built `npm run build` successfully into dist/. Manual click-through
confirmed each page works end-to-end (filters apply, tables sort,
links open).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Out of scope for sub-project 3

- GitHub Actions deploy workflow → sub-project 4 (CI)
- Custom theme / branding
- URL-encoded shareable filter state
- Per-cultivar permalink resolution from URL slugs
- Mobile-specific responsive tweaks
- Real-time updates / WebSocket
- Search-by-text auto-complete

---

## Self-review checklist

- [ ] All 8 tasks ticked
- [ ] `cd site && npm run build` produces `dist/` cleanly
- [ ] Every page (`/`, `/plants/`, `/cultivar/`, `/non-plants/`, `/nurseries/`, `/health/`) renders without errors
- [ ] Filters on `/plants/` work (table updates as user toggles)
- [ ] Links to RHS and nursery URLs open in new tabs
- [ ] `data/products_matched.parquet` is the source of truth — page table counts match `pl.read_parquet(...).height`
