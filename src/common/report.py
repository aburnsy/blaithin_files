"""Per-run scrape report + snapshot-diff alerts.

Each scraper produces a ScrapeReport; `snapshot_diff` compares today's parsed
count against the median of the past N reports and emits alerts on big drops.
Used by CI to surface silently-broken scrapers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from src.common.logging import get_logger

log = get_logger("scrapers.report")

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


@dataclass
class ScrapeReport:
    """A single scraper's run summary."""

    source: str
    run_date: date
    products_in: int = 0
    products_parsed: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    error_count: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "run_date": self.run_date.isoformat(),
            "products_in": self.products_in,
            "products_parsed": self.products_parsed,
            "dropped": self.dropped,
            "error_count": self.error_count,
            "duration_seconds": self.duration_seconds,
        }

    def write(self, *, dir_: Path | None = None) -> Path:
        """Append this report as a JSON line in reports/<date>.jsonl."""
        target_dir = dir_ or REPORTS_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        out = target_dir / f"{self.run_date.isoformat()}.jsonl"
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict()) + "\n")
        return out


def snapshot_diff(
    today: ScrapeReport,
    history: list[ScrapeReport],
    *,
    threshold: float = 0.25,
) -> list[str]:
    """Return a list of alert strings if today's count drops > threshold vs history median."""
    if not history:
        return []

    parsed_counts = sorted(r.products_parsed for r in history)
    n = len(parsed_counts)
    median = parsed_counts[n // 2] if n % 2 else (parsed_counts[n // 2 - 1] + parsed_counts[n // 2]) / 2

    if median == 0:
        return []

    drop_pct = (median - today.products_parsed) / median
    if drop_pct > threshold:
        return [f"{today.source}: parsed count dropped {drop_pct:.0%} (today: {today.products_parsed}, 7-day median: {median:.0f})"]
    return []
