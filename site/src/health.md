---
title: Health — scraper run reports
---

# Scraper health

Products parsed per nursery over time, plus a quick summary of the most recent run for each source.

```js
const reports = await FileAttachment("data/reports.json").json();
```

```js
if (reports.length === 0) {
  display(html`<p style="color:#666;font-style:italic;">No scrape runs recorded yet — reports appear here after the first successful run.</p>`);
} else {
  // Line chart: products_parsed over time, one line per source
  display(Plot.plot({
    title: "Products parsed per nursery over time",
    x: {label: "Run date", type: "utc"},
    y: {label: "Products parsed", grid: true},
    color: {legend: true, label: "Source"},
    marks: [
      Plot.lineY(reports, {
        x: d => new Date(d.run_date),
        y: "products_parsed",
        stroke: "source",
        tip: true,
        marker: "dot",
      }),
    ],
    marginRight: 140,
    width: 800,
  }));
}
```

```js
if (reports.length > 0) {
  // Build a "last run per source" summary
  const latestBySource = new Map();
  for (const r of reports) {
    const prev = latestBySource.get(r.source);
    if (!prev || r.run_date > prev.run_date) {
      latestBySource.set(r.source, r);
    }
  }
  const summaryRows = [...latestBySource.values()].sort((a, b) =>
    String(a.source).localeCompare(String(b.source))
  );

  display(html`<h2>Last run per source</h2>`);
  display(Inputs.table(summaryRows, {
    columns: ["source", "run_date", "products_in", "products_parsed", "error_count"],
    header: {
      source: "Source",
      run_date: "Run date",
      products_in: "Products in",
      products_parsed: "Products parsed",
      error_count: "Errors",
    },
    format: {
      run_date: x => x ? String(x).slice(0, 10) : "—",
      products_in: x => x != null ? x : "—",
      products_parsed: x => x != null ? x : "—",
      error_count: x => x != null ? x : "—",
    },
    multiple: false,
  }));
}
```
