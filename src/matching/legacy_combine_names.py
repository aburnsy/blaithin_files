"""DO NOT IMPORT — reference-only copy of the legacy combine-names transformer.

Source: blaithin/docker/blaithin/transformers/combine_common_and_botanical_names.py
(sister repo as of 2026-05-11)

This file exists as a documentation reference for sub-project 2 (matching v2).
The REPLACEMENT keeps RHS records as one row per (genus, species) with a
synonyms[] field, instead of flattening botanical and common names into a
single deduped column. See spec §6.1 for the new schema.

Importing this module will fail at runtime (mage_ai is not installed in this
venv). The file will be deleted at the end of sub-project 2.
"""

# ---- ORIGINAL CONTENT BELOW ----

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test
import polars as pl
from rapidfuzz.utils import default_process

@transformer
def transform(data, *args, **kwargs):
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

    data = pl.DataFrame(data)

    common_name_plants = data[['common_name','id']].drop_nulls().rename({"common_name": "name"})
    botanical_name_plants = data[['botanical_name','id']].drop_nulls().rename({"botanical_name": "name"})

    plants = pl.concat([common_name_plants,botanical_name_plants]).unique() # Unique here just in case there are dupes
    plants = plants.with_columns(
        pl.col('name').map_elements(lambda s: default_process(s)).str.replace("  ", " ").str.replace("  ", " ").str.strip()
    )
    # Remove duplicates on name
    plants = plants.groupby("name").agg(pl.col('id').sort().first())

    # Should we eventually only return one ID per name? We know we have duplicates for some

    return plants


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
