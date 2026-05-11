"""Import smoke test.

Locks in the current module layout so the consolidation refactor (sub-project 0)
cannot accidentally break the orchestrator's imports. After the refactor, the
"current path" tests below are removed and replaced with "new path" tests in
later tasks of this same sub-project.
"""


def test_bronze_scrapers_importable():
    from bronze import (
        arboretum,
        carragh,
        common,
        gardens4you,
        quickcrop,
        rhs,
        rhs_urls,
        tullys,
    )

    for module in (
        arboretum,
        carragh,
        common,
        gardens4you,
        quickcrop,
        rhs,
        rhs_urls,
        tullys,
    ):
        assert module is not None


def test_cloud_storage_importable():
    import cloud_storage

    assert hasattr(cloud_storage, "export_data_locally")
    assert hasattr(cloud_storage, "add_defaults_to_fields")


def test_orchestrator_importable():
    import load_bronze_data

    assert load_bronze_data is not None
