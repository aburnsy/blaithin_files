data_sources = [
    # Spring planting bulbs (summer-flowering) — single "all" page covers everything.
    ["https://www.peternyssen.com/spring-planting/all-spring-planting.html", "Bulbs"],
    # Autumn planting bulbs (spring-flowering) — no "all" page exists, so seed
    # the top-level subcategories. Overlap between these (e.g. "special-offers"
    # vs "tulips") is deduped downstream by product_url.
    ["https://www.peternyssen.com/autumn-planting/alliums.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/autumn-flowering-crocuses.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/crocuses.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/daffodils-narcissi.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/hyacinths.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/indoor-flowering-bulbs.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/irises.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/lilium-lilies.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/miscellaneous-bulbs.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/tulips.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/woodland-bulbs.html", "Bulbs"],
    ["https://www.peternyssen.com/autumn-planting/hardy-perennial-plants.html", "Perennials"],
    ["https://www.peternyssen.com/autumn-planting/perennial-tulips.html", "Bulbs"],
]
