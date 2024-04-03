import polars as pl
import pyarrow.parquet as pq
import datetime


def add_defaults_to_fields(
    df: pl.DataFrame, field_name: str, default_value
) -> pl.DataFrame:
    if field_name not in df.columns:
        print(f"Adding column {field_name} with default value {default_value}")
        return df.with_columns((pl.lit(default_value)).alias(field_name))
    else:
        return df


def export_data_locally(table: list[dict], dated: bool = True) -> None:
    # Easiest to use Polars to convert a list of dictionaries into a DF/Table
    df = pl.DataFrame(table)
    source = df.select(pl.first("source")).item()

    if dated:
        df = add_defaults_to_fields(df, field_name="product_code", default_value=None)
        df = add_defaults_to_fields(df, field_name="quantity", default_value=1)
        df = add_defaults_to_fields(
            df, field_name="input_date", default_value=datetime.date.today()
        )

        file_name = (
            f"data\\{source}\\{datetime.date.today().strftime('%Y-%m-%d')}.parquet"
        )
    else:
        file_name = f"data\\{source}.parquet"

    table = df.to_arrow()
    print(f"Storing data to file '{file_name}'")
    pq.write_table(table, file_name)
