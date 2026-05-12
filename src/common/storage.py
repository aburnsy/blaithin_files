import datetime
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq


def add_defaults_to_fields(
    df: pl.DataFrame, field_name: str, default_value
) -> pl.DataFrame:
    if field_name not in df.columns:
        print(f"Adding column {field_name} with default value {default_value}")
        return df.with_columns((pl.lit(default_value)).alias(field_name))
    else:
        return df


def export_data_locally(table: list[dict] | None, dated: bool = True) -> None:
    if not table:
        print("Scraper returned no data; skipping parquet write.")
        return

    # Easiest to use Polars to convert a list of dictionaries into a DF/Table
    df = pl.DataFrame(table)
    source = df.select(pl.first("source")).item()

    if dated:
        df = add_defaults_to_fields(df, field_name="product_code", default_value=None)
        df = add_defaults_to_fields(df, field_name="quantity", default_value=1)
        df = add_defaults_to_fields(
            df, field_name="input_date", default_value=datetime.date.today()
        )

        file_path = Path("data") / source / f"{datetime.date.today().strftime('%Y-%m-%d')}.parquet"
    else:
        file_path = Path("data") / f"{source}.parquet"

    file_path.parent.mkdir(parents=True, exist_ok=True)
    table = df.to_arrow()
    print(f"Storing data to file '{file_path}'")
    pq.write_table(table, file_path)
