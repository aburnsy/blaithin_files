import polars as pl
import os
from pathlib import Path
from datetime import datetime

folder_path = "data/gardens4you/"

max_date = max(
    [
        datetime.strptime(file_found.name.split(".")[0], "%Y-%m-%d")
        for file_found in Path(folder_path).glob("*.parquet")
    ]
).strftime("%Y-%m-%d")
df = pl.read_parquet(f"{folder_path}/{max_date}.parquet")

for file_found in Path(folder_path).glob("*.parquet"):
    date_value = file_found.name.split(".")[0]
    if date_value == max_date:
        continue
    print(date_value)
    df = df.with_columns((pl.lit(date_value)).alias("input_date"))
    print(df.sample(5))
    df.write_parquet(f"{folder_path}/{date_value}.parquet")
