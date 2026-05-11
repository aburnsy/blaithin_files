"""DO NOT IMPORT — reference-only copy of the legacy Mage AI matcher.

Source: blaithin/docker/blaithin/transformers/match_product_to_plant.py
(sister repo as of 2026-05-11)

This file exists as a documentation reference for sub-project 2 (matching v2),
which will REPLACE this approach with:
  - gnparser for botanical name parsing
  - exact (genus, species) lookup against RHS
  - rapidfuzz residual on synonyms + common names
  - LLM batch fallback for the long tail
  - cultivar preserved as a first-class column on the product row

Importing this module will fail at runtime (mage_ai is not installed in this
venv). The file will be deleted at the end of sub-project 2.
"""

# ---- ORIGINAL CONTENT BELOW ----

if "transformer" not in globals():
    from mage_ai.data_preparation.decorators import transformer
if "test" not in globals():
    from mage_ai.data_preparation.decorators import test
import polars as pl
from rapidfuzz import process
from rapidfuzz.distance import Levenshtein
from rapidfuzz.utils import default_process

# from thefuzz import process
# from rapidfuzz import fuzz

# from rapidfuzz.distance import Levenshtein, JaroWinkler


@transformer
def transform(plants, products, *args, **kwargs):
    """
    Template code for a transformer block.

    Add more parameters to this function if this block has multiple parent blocks.
    There should be one parameter for each output variable from each parent block.

    Args:
        data: The output from the upstream parent block
        args: The output from any additional upstream blocks (if applicable)

    Returns:
        Anything (e.g. data frame, dictionary, array, int, str, etc.)
    """
    # Specify your transformation logic here

    plant_values = plants.select("name").to_series(0).unique().to_list()
    distinct_products = products.select("product_name_cleansed").unique()

    matched_products = (
        distinct_products
        # .filter(pl.col('product_name_cleansed').str.contains("stoechas"))
        # .sample(100)
        .with_columns(
            pl.col("product_name_cleansed")
            .map_elements(
                lambda product_name: process.extractOne(
                    product_name,
                    # plant_list,
                    [
                        plant
                        for plant in plant_values
                        if (
                            any(
                                default_process(product_name.split()[0]) == e
                                for e in plant.split()
                            )
                        )
                    ],
                    scorer=Levenshtein.normalized_similarity,
                    score_cutoff=0.45,
                )
            )
            .alias("match")
        )
        .with_columns(pl.col("match").list.get(0).alias("name"))
        .drop("match")
        .with_columns(
            pl.when(pl.col("name").is_null())
            .then(
                pl.col("product_name_cleansed").map_elements(
                    lambda product_name: process.extractOne(
                        product_name,
                        plant_values,
                        scorer=Levenshtein.normalized_similarity,
                        score_cutoff=0.60,
                    )
                )
            )
            .otherwise(None)
            .alias("match")
        )
        .with_columns(pl.col("match").list.get(0).alias("name2"))
        .drop("match")
        .with_columns(
            pl.when(pl.col("name").is_null())
            .then(pl.col("name2"))
            .otherwise(pl.col("name"))
            .alias("name")
        )
        .drop("name2")
        .join(
            plants,
            on="name",
            how="inner",
        )  # Only return matches on products from rhs website
        .join(
            products,
            on="product_name_cleansed",
            how="inner",
        )
    )

    return matched_products


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, "The output is undefined"
