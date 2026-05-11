---
title: Cultivar detail
---

# Cultivar detail

Compare prices across all nurseries for a specific plant. Enter genus and species (and optionally cultivar) below, or link here with `?genus=Acer&species=palmatum&cultivar=Bloodgood`.

```js
const nurseries = await FileAttachment("data/nurseries.json").json();

const productsArrow = FileAttachment("data/products.parquet").parquet();
const rhsArrow = FileAttachment("data/rhs.parquet").parquet();
const db = await DuckDBClient.of({products: productsArrow, rhs: rhsArrow});
```

```js
// Prefill from URL query string if present
const params = new URLSearchParams(location.search);
const genus = view(Inputs.text({label: "Genus", value: params.get("genus") || "Acer", placeholder: "e.g. Acer"}));
const species = view(Inputs.text({label: "Species", value: params.get("species") || "palmatum", placeholder: "e.g. palmatum"}));
const cultivar = view(Inputs.text({label: "Cultivar (optional)", value: params.get("cultivar") || "", placeholder: "e.g. Bloodgood"}));
```

```js
const cultivarClause = cultivar && cultivar.trim() !== "" ? "AND p.cultivar = $3" : "";

const matches = await db.query(
  `SELECT
     p.source          AS nursery,
     p.product_name_raw,
     p.price_native,
     p.currency,
     p.price_eur,
     p.size,
     p.stock,
     p.product_url
   FROM products p
   WHERE lower(p.genus) = lower($1)
     AND lower(p.species) = lower($2)
     ${cultivarClause}
   ORDER BY COALESCE(p.price_eur, p.price_native)`,
  cultivar && cultivar.trim() !== ""
    ? [genus.trim(), species.trim(), cultivar.trim()]
    : [genus.trim(), species.trim()]
);
```

```js
const enriched = matches.toArray().map(row => {
  const cfg = nurseries[row.nursery] || {};
  const flatFee = (cfg.delivery_fees && cfg.delivery_fees[0]?.fee_eur) || 0;
  const basePrice = row.price_eur != null ? row.price_eur : (row.price_native || 0);
  const totalToDoor = basePrice + flatFee;
  return {
    ...row,
    delivery_eur: flatFee,
    min_order: cfg.min_order_eur || 0,
    vat_note: cfg.vat_included === false ? "VAT may apply at customs" : "",
    total_to_door_eur: totalToDoor,
  };
});
```

```js
Inputs.table(enriched, {
  columns: [
    "nursery", "product_name_raw",
    "price_native", "currency", "price_eur",
    "size", "stock",
    "delivery_eur", "min_order", "vat_note",
    "total_to_door_eur", "product_url"
  ],
  header: {
    nursery: "Nursery",
    product_name_raw: "Product",
    price_native: "Price",
    currency: "Cur",
    price_eur: "EUR",
    size: "Size",
    stock: "Stock",
    delivery_eur: "Delivery (€)",
    min_order: "Min order (€)",
    vat_note: "VAT note",
    total_to_door_eur: "Total to door (€)",
    product_url: "Buy"
  },
  format: {
    product_url: (x) => x ? html`<a href="${x}" target="_blank" rel="noopener">Buy ↗</a>` : "—",
    price_native: (x) => x != null ? x.toFixed(2) : "—",
    price_eur: (x) => x != null ? x.toFixed(2) : "—",
    delivery_eur: (x) => x != null ? x.toFixed(2) : "0.00",
    total_to_door_eur: (x) => x != null ? x.toFixed(2) : "—",
    min_order: (x) => x != null && x > 0 ? `€${x.toFixed(2)}` : "—",
    stock: (x) => x != null ? x : "—",
    vat_note: (x) => x || "—",
  },
  rows: 20,
  multiple: false
})
```
