"""Build a 200-row RHS subset for matching tests.

Picks rows that exercise different match paths:
- 50 with cultivars in the botanical_name (e.g. Rosa 'Irish Fireflame')
- 50 plain binomials (e.g. Acer palmatum)
- 50 with common_name populated
- 50 random
"""

from pathlib import Path

import polars as pl

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "rhs_sample.parquet"
SRC = Path(__file__).resolve().parents[1] / "data" / "rhs.parquet"


def main():
    df = pl.read_parquet(SRC)

    with_cultivar = df.filter(pl.col("botanical_name").str.contains("'")).sample(50, seed=1)
    plain = df.filter(~pl.col("botanical_name").str.contains("'")).sample(50, seed=2)
    with_common = df.filter(pl.col("common_name").is_not_null()).sample(50, seed=3)
    random = df.sample(50, seed=4)

    sample = (
        pl.concat([with_cultivar, plain, with_common, random])
        .unique(subset=["id"])
        .rename({"id": "rhs_id"})  # fixture uses the new (post-Task-16) schema name
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sample.write_parquet(OUT)
    print(f"Wrote {len(sample)} rows to {OUT}")


if __name__ == "__main__":
    main()
