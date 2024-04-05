import polars as pl
import pyarrow.dataset as ds
import os
from pathlib import Path
# df = pl.scan_parquet(
#     "./data/rhs/1.parquet",
# )
# df = df.collect()
# print(df)


# df = pl.scan_pyarrow_dataset(ds.dataset("data/rhs/")).collect()
# print(df)
# df = pl.read_parquet("data/rhs.parquet")
# df = df.filter(pl.col("id").is_null())
# print(df)

# os.remove(file_full_name)

lazydf = []

basepath = Path("data/rhs/")
for myfile in basepath.iterdir():
    try:
        length = (
            pl.scan_parquet(myfile)
            .select("id")
            .filter(pl.col("id").is_null())
            .select(pl.len())
            .collect()
            .item()
        )
        if length == 0:
            continue
        print(f"Length {length} for file {myfile.name}")

    except pl.exceptions.ColumnNotFoundError:
        print(f"Length {length} for file {myfile.name}")

    file_path = myfile.resolve()
    os.remove(file_path)
