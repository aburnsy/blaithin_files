---
title: Plants — search & compare
---

# Plants

Filter by growing conditions, sort by any column, click through to RHS or the nursery's product page.

```js
const productsArrow = FileAttachment("data/products.parquet").parquet();
const rhsArrow = FileAttachment("data/rhs.parquet").parquet();
```

```js
const db = await DuckDBClient.of({products: productsArrow, rhs: rhsArrow});
```

```js
// Filter inputs
const sunInput = Inputs.checkbox(
  ["Full sun", "Partial shade", "Full shade"],
  {label: "Sun exposure"}
);
const sun = view(sunInput);
```

```js
const hardiness = view(Inputs.range([1, 10], {
  label: "Min hardiness (H rating)",
  value: 1,
  step: 1
}));
```

```js
const inStock = view(Inputs.toggle({label: "In stock only", value: false}));
```

```js
// Build the filter clause from reactive inputs
const sunFilter = sun && sun.length > 0
  ? `AND (${sun.map((s) => `list_contains(r.sun_exposure, '${s.replace("'", "''")}')`).join(" OR ")})`
  : "";

const hardinessFilter = hardiness > 1
  ? `AND TRY_CAST(regexp_extract(r.hardiness, '[0-9]+') AS INTEGER) >= ${hardiness}`
  : "";

const stockFilter = inStock
  ? `AND p.stock IS NOT NULL AND p.stock > 0`
  : "";

const filtered = await db.query(`
  SELECT
    p.genus,
    p.species,
    p.cultivar,
    p.product_name_raw,
    p.source        AS nursery,
    p.price_native,
    p.currency,
    p.price_eur,
    p.size,
    p.stock,
    p.product_url,
    r.common_names,
    r.plant_url     AS rhs_url,
    r.hardiness,
    r.sun_exposure
  FROM products p
  LEFT JOIN rhs r ON p.rhs_id = r.rhs_id
  WHERE p.is_plant = true
  ${sunFilter}
  ${hardinessFilter}
  ${stockFilter}
  ORDER BY p.genus, p.species, p.cultivar, p.price_native
`);
```

```js
Inputs.table(filtered, {
  columns: [
    "genus", "species", "cultivar",
    "nursery", "price_native", "currency", "price_eur",
    "size", "stock",
    "rhs_url", "product_url"
  ],
  header: {
    genus: "Genus",
    species: "Species",
    cultivar: "Cultivar",
    nursery: "Nursery",
    price_native: "Price",
    currency: "Cur",
    price_eur: "EUR",
    size: "Size",
    stock: "Stock",
    rhs_url: "RHS",
    product_url: "Buy"
  },
  format: {
    rhs_url: (x) => x ? html`<a href="${x}" target="_blank" rel="noopener">RHS ↗</a>` : "—",
    product_url: (x) => x ? html`<a href="${x}" target="_blank" rel="noopener">Buy ↗</a>` : "—",
    price_native: (x) => x != null ? x.toFixed(2) : "—",
    price_eur: (x) => x != null ? x.toFixed(2) : "—",
    stock: (x) => x != null ? x : "—",
  },
  rows: 20,
  multiple: false
})
```
