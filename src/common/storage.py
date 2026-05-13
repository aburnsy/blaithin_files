import datetime
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq

from src.common.nurseries import load_nurseries

IE_VAT_RATE = 0.23


def add_defaults_to_fields(
    df: pl.DataFrame, field_name: str, default_value
) -> pl.DataFrame:
    if field_name not in df.columns:
        print(f"Adding column {field_name} with default value {default_value}")
        return df.with_columns((pl.lit(default_value)).alias(field_name))
    else:
        return df


def _apply_vat_if_needed(df: pl.DataFrame, source: str) -> pl.DataFrame:
    # Sites flagged vat_included=false (currently Tullys trade portal and
    # GreenGardenFlowerBulbs) list ex-VAT prices; Irish customers pay 23%
    # on top, so we bake that into the bronze price column. Older scrapers
    # use "price"; newer Shopify/Woo/Magento bases use "price_native".
    #
    # If config loading fails we MUST NOT silently write ex-VAT data for a
    # source that's flagged vat_included=false — that produced wrong Tullys
    # prices once already. Raise loudly instead.
    try:
        cfg = load_nurseries().get(source)
    except Exception as exc:
        raise RuntimeError(
            f"Cannot load nurseries config while writing {source!r}: {exc}. "
            "Refusing to write — would silently skip VAT for any ex-VAT source."
        ) from exc
    if cfg is None or cfg.vat_included:
        return df
    price_col = next((c for c in ("price", "price_native") if c in df.columns), None)
    if price_col is None:
        return df
    print(f"Applying IE VAT @ {IE_VAT_RATE:.0%} to {source} (ex-VAT source)")
    return df.with_columns((pl.col(price_col) * (1 + IE_VAT_RATE)).alias(price_col))


def export_data_locally(table: list[dict] | None, dated: bool = True) -> None:
    if not table:
        print("Scraper returned no data; skipping parquet write.")
        return

    # Easiest to use Polars to convert a list of dictionaries into a DF/Table.
    # ``infer_schema_length=None`` scans all rows so a column that's None for
    # the first ~100 rows and a string later doesn't crash schema inference.
    df = pl.DataFrame(table, infer_schema_length=None)
    source = df.select(pl.first("source")).item()
    df = _apply_vat_if_needed(df, source)

    if dated:
        df = add_defaults_to_fields(df, field_name="product_code", default_value=None)
        df = add_defaults_to_fields(df, field_name="quantity", default_value=1)
        df = add_defaults_to_fields(
            df, field_name="input_date", default_value=datetime.date.today()
        )

        file_path = Path("data") / source / "data.parquet"
    else:
        file_path = Path("data") / f"{source}.parquet"

    file_path.parent.mkdir(parents=True, exist_ok=True)
    table = df.to_arrow()
    print(f"Storing data to file '{file_path}'")
    pq.write_table(table, file_path)
