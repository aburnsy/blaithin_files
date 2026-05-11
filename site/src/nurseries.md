---
title: Nurseries — overview
---

# Nurseries

One row per nursery: display name, currency, delivery config, min order, VAT note, last-scraped date and product counts.

```js
const nurseries = await FileAttachment("data/nurseries.json").json();

const productsArrow = FileAttachment("data/products.parquet").parquet();
const db = await DuckDBClient.of({products: productsArrow});
```

```js
// Aggregate product counts from the parquet, grouped by nursery key (source)
const counts = await db.query(`
  SELECT
    source,
    COUNT(*)                                        AS total,
    COUNT(*) FILTER (WHERE is_plant = true)         AS plants,
    COUNT(*) FILTER (WHERE is_plant = false)        AS non_plants,
    MAX(input_date)                                 AS last_scraped
  FROM products
  GROUP BY source
`);
```

```js
// Build a lookup map: source key -> {total, plants, non_plants, last_scraped}
const countsBySource = new Map(
  counts.toArray().map(row => [row.source, row])
);

// LEFT join: every nursery in the config appears, even with zero products
const rows = Object.entries(nurseries).map(([key, cfg]) => {
  const agg = countsBySource.get(key);
  return {
    display_name: cfg.display_name,
    base_url: cfg.base_url,
    currency: cfg.currency,
    delivery_type: cfg.delivery_type,
    min_order: cfg.min_order_eur > 0 ? cfg.min_order_eur : null,
    vat_note: cfg.vat_included === false ? "VAT may apply" : "Incl.",
    runs_on: cfg.runs_on,
    total: agg ? Number(agg.total) : 0,
    plants: agg ? Number(agg.plants) : 0,
    non_plants: agg ? Number(agg.non_plants) : 0,
    last_scraped: agg && agg.last_scraped ? agg.last_scraped : null,
  };
});
```

```js
Inputs.table(rows, {
  columns: [
    "display_name", "base_url",
    "currency", "delivery_type", "min_order", "vat_note",
    "runs_on",
    "total", "plants", "non_plants",
    "last_scraped"
  ],
  header: {
    display_name: "Nursery",
    base_url: "Website",
    currency: "Cur",
    delivery_type: "Delivery",
    min_order: "Min order (€)",
    vat_note: "VAT",
    runs_on: "Scraper",
    total: "Products",
    plants: "Plants",
    non_plants: "Non-plants",
    last_scraped: "Last scraped"
  },
  format: {
    base_url: (x) => x ? html`<a href="${x}" target="_blank" rel="noopener">${x}</a>` : "—",
    min_order: (x) => x != null ? `€${x.toFixed(2)}` : "—",
    last_scraped: (x) => x != null ? String(x).slice(0, 10) : "—",
    total: (x) => x != null ? x : 0,
    plants: (x) => x != null ? x : 0,
    non_plants: (x) => x != null ? x : 0,
  },
  rows: 20,
  multiple: false
})
```
