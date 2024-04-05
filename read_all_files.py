import polars as pl
import pyarrow.dataset as ds

# df = pl.scan_pyarrow_dataset(ds.dataset("data/rhs/")).collect()
# print(df)
# df.write_parquet("data/rhs.parquet")

df = pl.read_parquet("data/rhs.parquet")
print(df)

df = pl.read_parquet("data/rhs_urls.parquet")
print(df)
