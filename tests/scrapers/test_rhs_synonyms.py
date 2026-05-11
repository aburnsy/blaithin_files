"""Test that the RHS scraper extracts synonyms from a real page fixture."""

from pathlib import Path

from bs4 import BeautifulSoup

from src.scrapers.rhs import extract_detailed_plant_data


def test_extracts_synonyms_when_present():
    html = (Path(__file__).resolve().parents[1] / "fixtures" / "rhs_html" / "deschampsia-cespitosa.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    plant = {"id": 5638, "plant_url": "https://www.rhs.org.uk/plants/5638/deschampsia-cespitosa/details"}
    extract = extract_detailed_plant_data(plant, soup)
    assert "synonyms" in extract
    assert isinstance(extract["synonyms"], list)
