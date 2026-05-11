"""Import smoke test.

Locks in the current module layout so the consolidation refactor (sub-project 0)
cannot accidentally break the orchestrator's imports. After the refactor, the
"current path" tests below are removed and replaced with "new path" tests in
later tasks of this same sub-project.
"""

import importlib


def test_scrapers_importable():
    for name in (
        "src.scrapers.arboretum",
        "src.scrapers.carragh",
        "src.scrapers.common",
        "src.scrapers.gardens4you",
        "src.scrapers.quickcrop",
        "src.scrapers.rhs",
        "src.scrapers.rhs_urls",
        "src.scrapers.tullys",
    ):
        importlib.import_module(name)


def test_cloud_storage_importable():
    cloud_storage = importlib.import_module("cloud_storage")

    assert hasattr(cloud_storage, "export_data_locally")
    assert hasattr(cloud_storage, "add_defaults_to_fields")


def test_orchestrator_importable():
    importlib.import_module("load_bronze_data")
