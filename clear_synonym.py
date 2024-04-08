import polars as pl
import os
from pathlib import Path

lazydf = []

basepath = Path("data/rhs/")
for myfile in basepath.iterdir():
    length = (
        pl.scan_parquet(myfile)
        .select(["botanical_name", "plant_type"])
        .filter(pl.col("botanical_name").str.starts_with("Deschampsia"))
        .filter(~pl.col("plant_type").list.contains("Grass Like"))
        .select(pl.len())
        .collect()
        .item()
    )
    if length == 0:
        continue
    else:
        df = (
            pl.scan_parquet(myfile)
            .select(["botanical_name", "plant_type"])
            .filter(pl.col("botanical_name").str.starts_with("Deschampsia"))
            .collect()
        )
        print(df)
        # print(f"Removing file {myfile.name}")
        file_path = myfile.resolve()
        os.remove(file_path)

# 62755
