"""Tests for scrape report and snapshot diff."""

from datetime import date

from src.common.report import ScrapeReport, snapshot_diff


def test_report_init():
    r = ScrapeReport(source="tullys", run_date=date(2026, 5, 11))
    assert r.source == "tullys"
    assert r.products_in == 0
    assert r.products_parsed == 0
    assert r.dropped == {}


def test_report_increment():
    r = ScrapeReport(source="tullys", run_date=date(2026, 5, 11))
    r.products_in += 100
    r.products_parsed += 95
    r.dropped["missing_price"] = 3
    r.dropped["parse_error"] = 2
    assert r.products_parsed == 95
    assert sum(r.dropped.values()) == 5


def test_snapshot_diff_no_history():
    today = ScrapeReport(source="tullys", run_date=date(2026, 5, 11), products_parsed=100)
    alerts = snapshot_diff(today, history=[])
    assert alerts == []


def test_snapshot_diff_within_threshold():
    today = ScrapeReport(source="tullys", run_date=date(2026, 5, 11), products_parsed=110)
    history = [
        ScrapeReport(source="tullys", run_date=date(2026, 5, 4 + i), products_parsed=100)
        for i in range(7)
    ]
    alerts = snapshot_diff(today, history, threshold=0.25)
    assert alerts == []


def test_snapshot_diff_exceeds_threshold():
    today = ScrapeReport(source="tullys", run_date=date(2026, 5, 11), products_parsed=50)  # 50% drop
    history = [
        ScrapeReport(source="tullys", run_date=date(2026, 5, 4 + i), products_parsed=100)
        for i in range(7)
    ]
    alerts = snapshot_diff(today, history, threshold=0.25)
    assert len(alerts) == 1
    assert "tullys" in alerts[0]
    assert "50%" in alerts[0] or "0.5" in alerts[0]
