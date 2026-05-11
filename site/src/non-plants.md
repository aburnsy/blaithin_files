---
title: Non-plants — compost, tools, pots & more
---

# Non-plant products

Filter by category, sort by any column, click through to the nursery product page.

```js
const productsArrow = FileAttachment("data/products.parquet").parquet();
```

```js
const db = await DuckDBClient.of({products: productsArrow});
```

```js
// Category filter — all selected by default
const ALL_CATEGORIES = ["compost", "soil", "tool", "pot", "fertiliser", "accessory", "other"];
const categoryInput = Inputs.checkbox(
  ALL_CATEGORIES,
  {label: "Category", value: ALL_CATEGORIES}
);
const category = view(categoryInput);
```

```js
const inStock = view(Inputs.toggle({label: "In stock only", value: false}));
```

```js
// Build filter clauses from reactive inputs
const categoryFilter = category && category.length > 0
  ? `AND p.product_category IN (${category.map((c) => `'${c.replace("'", "''")}'`).join(", ")})`
  : "AND false";

const stockFilter = inStock
  ? `AND p.stock IS NOT NULL AND p.stock > 0`
  : "";

const filtered = await db.query(`
  SELECT
    p.source           AS nursery,
    p.product_name_raw,
    p.product_category AS category,
    p.price_native,
    p.currency,
    p.price_eur,
    p.size,
    p.stock,
    p.product_url
  FROM products p
  WHERE p.is_plant = false
  ${categoryFilter}
  ${stockFilter}
  ORDER BY p.product_category, p.price_native
`);
```

```js
Inputs.table(filtered, {
  columns: [
    "nursery", "product_name_raw", "category",
    "price_native", "currency", "price_eur",
    "size", "stock", "product_url"
  ],
  header: {
    nursery: "Nursery",
    product_name_raw: "Product",
    category: "Category",
    price_native: "Price",
    currency: "Cur",
    price_eur: "EUR",
    size: "Size",
    stock: "Stock",
    product_url: "Buy"
  },
  format: {
    product_url: (x) => x ? html`<a href="${x}" target="_blank" rel="noopener">Buy ↗</a>` : "—",
    price_native: (x) => x != null ? x.toFixed(2) : "—",
    price_eur: (x) => x != null ? x.toFixed(2) : "—",
    stock: (x) => x != null ? x : "—",
  },
  rows: 20,
  multiple: false
})
```
