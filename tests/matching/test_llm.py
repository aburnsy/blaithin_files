"""Tests for the LLM batch resolver (with mocked Anthropic client)."""

from unittest.mock import MagicMock, patch

import pytest

from src.matching.llm import batch_resolve
from src.matching.models import MatchOverride


@patch("src.matching.llm.Anthropic")
def test_batch_resolve_returns_overrides(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='[{"product_name_clean":"acer palmatum bloodgood","rhs_id":12345,"cultivar":"Bloodgood","is_plant":true,"product_category":"plant","confidence":0.95,"reasoning":"clear cultivar"}]')]
    )
    rhs_candidates = {12345: {"genus": "Acer", "species": "palmatum", "common_names": ["Japanese Maple"], "synonyms": []}}
    overrides = batch_resolve(["acer palmatum bloodgood"], rhs_candidates)
    assert len(overrides) == 1
    assert isinstance(overrides[0], MatchOverride)
    assert overrides[0].rhs_id == 12345
    assert overrides[0].cultivar == "Bloodgood"
    assert overrides[0].source == "llm"


@patch("src.matching.llm.Anthropic")
def test_batch_resolve_handles_no_match(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='[{"product_name_clean":"unknown thing","rhs_id":null,"is_plant":false,"product_category":"other","confidence":0.5,"reasoning":"not a plant"}]')]
    )
    overrides = batch_resolve(["unknown thing"], {})
    assert overrides[0].rhs_id is None
    assert overrides[0].is_plant is False
    assert overrides[0].product_category == "other"
