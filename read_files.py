import pyarrow.dataset as ds
import polars as pl

df = pl.scan_pyarrow_dataset(ds.dataset("data/tullys/")).collect()

# print(df)

# stock = df.select(pl.col("stock").cast(pl.Int64)).unique().to_series(0).to_list()

# print(stock)

print(df.schema)
