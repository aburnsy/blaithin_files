"""Unit tests for product name normalization."""

import json
from pathlib import Path

import pytest

from src.matching.normalize import clean_product_name

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "products_sample.json"


@pytest.mark.parametrize("case", json.loads(FIXTURE.read_text()))
def test_clean_product_name(case):
    if case["expected_clean"] is None:
        pytest.skip("expected_clean not yet annotated for this sample")
    assert clean_product_name(case["raw"]) == case["expected_clean"]


def test_clean_strips_pot_codes():
    assert clean_product_name("Acer palmatum 9cm") == "Acer palmatum"
    assert clean_product_name("Acer palmatum 2L") == "Acer palmatum"
    assert clean_product_name("Acer palmatum 3 ltr") == "Acer palmatum"
    assert clean_product_name("Acer palmatum P9") == "Acer palmatum"


def test_clean_strips_quantity_packs():
    assert clean_product_name("Tulipa 'Apricot Beauty' 5 bulbs") == "Tulipa 'Apricot Beauty'"
    assert clean_product_name("Pack of 10 Tulipa 'Apricot Beauty'") == "Tulipa 'Apricot Beauty'"


def test_clean_strips_common_name_parenthetical():
    assert clean_product_name("Hedera helix (English Ivy)") == "Hedera helix"
    assert clean_product_name("Olea europaea (Olive)") == "Olea europaea"
    assert clean_product_name("Olea europaea (G)") == "Olea europaea"
    assert clean_product_name("Acer palmatum ( )") == "Acer palmatum"


def test_clean_preserves_cultivar_group_parenthetical():
    # gnparser uses "(... Group)" to extract cultivar_group, so we must NOT strip these.
    assert (
        clean_product_name("Acer palmatum (Atropurpureum Group)")
        == "Acer palmatum (atropurpureum group)"
    )


def test_clean_preserves_cultivar_quotes():
    assert clean_product_name("Acer palmatum 'Bloodgood'") == "Acer palmatum 'Bloodgood'"


def test_clean_handles_extra_whitespace():
    assert clean_product_name("  Acer   palmatum  ") == "Acer palmatum"


def test_clean_strips_topiary_form_descriptors():
    assert clean_product_name("Olea europaea Half Standard 60- Ball") == "Olea europaea"
    assert clean_product_name("Olea europaea Pompon 200/250") == "Olea europaea"
    assert clean_product_name("Olea europaea Branched 140/160 Old Skin Extra") == "Olea europaea"
    assert clean_product_name("OLEA europaea Stem 40 Young Skin BONSAI") == "Olea europaea"
    assert clean_product_name("Olea europaea 1/4 Standard Stem Crown 30-") == "Olea europaea"
    assert clean_product_name("Carpinus betulus Pleached Panel") == "Carpinus betulus"
    assert clean_product_name("Betula alba Specimen Multi-Stem") == "Betula alba"


def test_clean_strips_bare_size_ranges():
    assert clean_product_name("Acer palmatum 10/12") == "Acer palmatum"
    assert clean_product_name("Olea europaea 120/150") == "Olea europaea"
    assert clean_product_name("Olea europaea 100") == "Olea europaea"


def test_clean_preserves_quoted_cultivar_with_form_word():
    # A "Standard" inside cultivar quotes must not be stripped.
    assert (
        clean_product_name("Rosa 'Standard Bearer' Bush")
        == "Rosa 'Standard Bearer'"
    )


def test_clean_case_folds_to_canonical():
    # Same plant, three different casings → one canonical key.
    canonical = clean_product_name("Olea europaea")
    assert clean_product_name("OLEA europaea") == canonical
    assert clean_product_name("Olea Europaea") == canonical
    assert clean_product_name("olea europaea") == canonical
    assert canonical == "Olea europaea"


def test_clean_strips_slash_suffix():
    assert (
        clean_product_name("Olea Europaea / Olive Trees girth")
        == "Olea europaea"
    )
    assert (
        clean_product_name("Bamboo Phyllostachys Aureocalis / Yellow groove bamboo")
        == "Bamboo phyllostachys aureocalis"
    )


def test_clean_strips_quantity_multiplier_but_not_hybrid_marker():
    assert clean_product_name("Aquilegia Ruby Port x 3") == "Aquilegia ruby port"
    # Botanical hybrid "x" + lowercase species must be preserved.
    assert (
        clean_product_name("Pinus x leucodermis")
        == "Pinus x leucodermis"
    )


def test_clean_normalises_unicode_and_fffd():
    # Smart quotes and replacement char get cleaned.
    assert clean_product_name("Osmanthus � Burkwoodii") == "Osmanthus burkwoodii"


def test_clean_is_idempotent():
    sample = "OLEA europaea Pompon 200/250 (Olive)"
    once = clean_product_name(sample)
    twice = clean_product_name(once)
    assert once == twice


def test_clean_strips_compound_dimension_tokens():
    # Letter-prefixed compound dimensions ("h120xw120cm") were leaking through
    # because \b\d+ requires a word boundary before the digit, which a leading
    # letter doesn't provide. All four of these collapse to the same plant.
    canonical = "Ilex aquifolium nellie r.stevens"
    assert clean_product_name("Ilex aquifolium Nellie R.Stevens H120xW120cm") == canonical
    assert clean_product_name("Ilex aquifolium Nellie R.Stevens 80cm") == canonical
    assert clean_product_name("Ilex aquifolium Nellie R.Stevens 100+cm") == canonical
    assert clean_product_name("Ilex aquifolium Nellie R.Stevens Cone") == canonical
    # Variants on the same dimension shape
    assert clean_product_name("Prunus lusitanica Angustifolia D20+cm") == "Prunus lusitanica angustifolia"
    assert clean_product_name("Prunus lusitanica Angustifolia D30cm+") == "Prunus lusitanica angustifolia"


def test_clean_strips_trailing_single_letter_size_token():
    # Nurseries tack on " T" (topiary), " P", etc. on the end of names.
    assert clean_product_name("Aster frikartii Monch T") == "Aster frikartii monch"
    assert clean_product_name("Diosma ericoides Pink Fountain T") == "Diosma ericoides pink fountain"


def test_clean_strips_stray_plus_sign():
    assert clean_product_name("Ilex mes. Blue Maid +") == "Ilex mes. blue maid"


def test_clean_strips_topiary_shape_descriptors():
    # Cone/spiral/pyramid/column are form descriptors like Pompon — they should
    # be dropped so a 'Cone' variant doesn't fork the cache key.
    assert clean_product_name("Buxus sempervirens Spiral") == "Buxus sempervirens"
    assert clean_product_name("Taxus baccata Pyramid") == "Taxus baccata"
    assert clean_product_name("Buxus sempervirens Column") == "Buxus sempervirens"


def test_clean_does_not_strip_unit_inside_word():
    # The leftover-unit pattern must not eat 'cm' from inside a real word like
    # 'Carolina' — assert genus + species both survive intact.
    assert clean_product_name("Carolina rosea") == "Carolina rosea"
