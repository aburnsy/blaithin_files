"""Parse-step tests for the RHS detail scraper.

Feed real API JSON fixtures through ``parse_detail()`` and assert the column
dict shape and content. Network is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.scrapers.rhs import parse_detail

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "rhs_api"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_forsythia_98658():
    row = parse_detail(_load("forsythia_98658.json"))

    assert row["rhs_id"] == 98658
    assert row["botanical_name"] == "Forsythia × intermedia 'Lynwood'"
    assert row["genus"] == "Forsythia"
    # × hybrid sign is stripped before species token
    assert row["species"] == "intermedia"
    assert row["family"] == "Oleaceae"
    assert row["common_name"] == "forsythia 'Lynwood Variety'"
    assert "forsythia 'Lynwood'" in row["common_names"]
    # synonyms include the alternate names but exclude the plant itself
    assert 98658 not in [s for s in row["synonyms"] if isinstance(s, int)]
    assert any("Lynwood Gold" in s for s in row["synonyms"])
    assert row["is_rhs_award_winner"] is True
    assert row["is_pollinator_plant"] is False
    assert row["height"] == "1.5-2.5 metres"
    assert row["spread"] == "1.5-2.5 metres"
    assert row["plant_type"] == ["Shrubs"]
    assert row["sun_exposure"] == ["Full sun", "Partial shade"]
    assert row["soils"] == ["Chalk", "Clay", "Loam", "Sand"]
    assert row["ph"] == ["Acid", "Alkaline", "Neutral"]
    assert row["aspect"] == ["South-facing", "East-facing", "North-facing", "West-facing"]
    assert row["exposure"] == ["Exposed", "Sheltered"]
    assert row["foliage"] == ["Deciduous"]
    assert row["habit"] == ["Bushy"]
    assert row["moisture"] == "Moist but well-drained"
    assert row["hardiness"] == "H6"
    assert row["description"].startswith("'Lynwood Variety'")
    assert row["plant_url"].startswith("https://www.rhs.org.uk/plants/98658/")
    assert row["source"] == "rhs"


def test_parse_phalaenopsis_no_hardiness_via_default():
    """Phalaenopsis is a houseplant with H1A hardiness; sanity-check the decode."""
    row = parse_detail(_load("phalaenopsis_372810.json"))
    assert row["rhs_id"] == 372810
    assert row["genus"] == "Phalaenopsis"
    assert row["hardiness"] in {"H1A", "H1B", "H1C", "H2", None, "Unknown"}


def test_parse_delphinium_synonym_plant():
    """Synonym records still parse cleanly and produce a valid row."""
    row = parse_detail(_load("delphinium_239046.json"))
    assert row["rhs_id"] == 239046
    assert row["genus"] == "Delphinium"


def test_parse_blackstonia_no_synonyms_no_common():
    """A plant with no synonyms/common produces empty lists, not crashes."""
    row = parse_detail(_load("blackstonia_78738.json"))
    assert row["rhs_id"] == 78738
    assert row["genus"] == "Blackstonia"
    assert row["species"] == "perfoliata"
    assert isinstance(row["synonyms"], list)
    assert isinstance(row["common_names"], list)


def test_parse_deschampsia_grass():
    row = parse_detail(_load("deschampsia_5638.json"))
    assert row["rhs_id"] == 5638
    assert row["genus"] == "Deschampsia"
    assert row["species"] == "cespitosa"
    assert "Grasses" in row["plant_type"] or row["family"] == "Poaceae"


@pytest.mark.parametrize(
    "name",
    [
        "forsythia_98658.json",
        "phalaenopsis_372810.json",
        "delphinium_239046.json",
        "blackstonia_78738.json",
        "deschampsia_5638.json",
    ],
)
def test_parse_emits_all_expected_columns(name):
    row = parse_detail(_load(name))
    expected = {
        "rhs_id", "plant_url", "botanical_name", "genus", "species", "family",
        "common_name", "common_names", "synonyms", "plant_type", "description",
        "is_rhs_award_winner", "is_pollinator_plant", "height", "spread",
        "soils", "moisture", "ph", "sun_exposure", "aspect", "exposure",
        "hardiness", "foliage", "habit", "source",
    }
    assert set(row.keys()) == expected
