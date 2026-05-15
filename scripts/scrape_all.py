"""Run all nursery scrapers locally with a fixed concurrency.

Mirrors the GitHub Actions nightly matrix (one site per parallel job),
but on the local machine with a configurable worker count.

Each site runs as a separate subprocess invoking
``python load_bronze_data.py --site <name>``.  Each subprocess writes its
own structlog file to ``logs/<site>.log`` (overwritten each run); the
parent process prints a one-line start/finish status for each site and a
final summary table.

Usage (PowerShell or bash)::

    python scripts/scrape_all.py                         # all sites, -j 3
    python scripts/scrape_all.py -j 5                    # custom concurrency
    python scripts/scrape_all.py --sites tullys,quickcrop
    python scripts/scrape_all.py --force                 # bypass freshness gate
    python scripts/scrape_all.py --list-sites

Honours the same env vars as ``load_bronze_data.py`` (``FORCE_SCRAPE``,
``SCRAPE_MAX_AGE_DAYS``) — set them in the parent shell and they propagate
to every subprocess.  ``--force`` is sugar for ``FORCE_SCRAPE=1``.

Exit code is the number of failed sites (0 = all OK, capped at 255).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.freshness import should_scrape  # noqa: E402
from src.common.nurseries import scraped_nursery_slugs  # noqa: E402

# Single source of truth — config/nurseries.yaml entries with `runs_on:
# github-actions`. Same list driving load_bronze_data.py's freshness gate
# and matching loop.
ALL_SITES: tuple[str, ...] = scraped_nursery_slugs()


def _max_age_days_from_env(default: int = 30) -> int:
    raw = os.environ.get("SCRAPE_MAX_AGE_DAYS")
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def run_site(
    site: str, log_dir: Path, force: bool
) -> tuple[str, int, float, Path]:
    """Run one scraper subprocess. Returns (site, returncode, elapsed_s, log_path).

    The subprocess writes its own structlog file to ``log_dir/<site>.log``
    via ``src.common.logging.configure(source=site)``. We just suppress its
    stdout/stderr (already captured to the log) and watch its exit code.
    """
    log_path = log_dir / f"{site}.log"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if force:
        env["FORCE_SCRAPE"] = "1"

    cmd = [sys.executable, "load_bronze_data.py", "--site", site]
    started = time.monotonic()
    rel_log = log_path.relative_to(REPO_ROOT)
    print(f"[start] {site:<12} -> {rel_log}", flush=True)

    proc = subprocess.Popen(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    returncode = proc.wait()

    elapsed = time.monotonic() - started
    tag = "ok" if returncode == 0 else f"FAIL rc={returncode}"
    print(f"[done ] {site:<12} {tag} in {elapsed:.1f}s", flush=True)
    return site, returncode, elapsed, log_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-j",
        "--concurrency",
        type=int,
        default=3,
        help="Number of sites to scrape in parallel (default: 3).",
    )
    parser.add_argument(
        "--sites",
        default=",".join(ALL_SITES),
        help=f"Comma-separated list of sites (default: all). Choices: {','.join(ALL_SITES)}.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass the freshness gate (sets FORCE_SCRAPE=1 for every subprocess).",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        help="Where to put per-site logs (default: logs/).",
    )
    parser.add_argument(
        "--list-sites",
        action="store_true",
        help="Print available sites and exit.",
    )
    args = parser.parse_args(argv)

    if args.list_sites:
        for s in ALL_SITES:
            print(s)
        return 0

    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    unknown = [s for s in sites if s not in ALL_SITES]
    if unknown:
        parser.error(
            f"Unknown site(s): {', '.join(unknown)}.  Valid: {', '.join(ALL_SITES)}"
        )
    if not sites:
        parser.error("No sites selected.")
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    log_dir = args.logs_dir or REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Pre-filter sites through the freshness gate so skipped nurseries never
    # spawn a subprocess and never overwrite logs/<site>.log.
    max_age = _max_age_days_from_env()
    skipped: list[tuple[str, str]] = []
    to_scrape: list[str] = []
    for s in sites:
        run, reason = should_scrape(s, max_age_days=max_age, force=args.force)
        if run:
            to_scrape.append(s)
        else:
            skipped.append((s, reason))

    print(
        f"Scraping {len(to_scrape)} site(s) with concurrency {args.concurrency} "
        f"({len(skipped)} skipped by freshness gate)"
    )
    print(f"Logs:    {log_dir}")
    if args.force:
        print("Force:   FORCE_SCRAPE=1 (freshness gate bypassed)")
    print()

    if not to_scrape:
        return 0

    sites = to_scrape

    overall_start = time.monotonic()
    by_site: dict[str, tuple[str, int, float, Path]] = {}
    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {pool.submit(run_site, s, log_dir, args.force): s for s in sites}
            for fut in as_completed(futures):
                site, rc, elapsed, log_path = fut.result()
                by_site[site] = (site, rc, elapsed, log_path)
    except KeyboardInterrupt:
        print("\nInterrupted — waiting for in-flight subprocesses to exit...", flush=True)
        raise

    overall_elapsed = time.monotonic() - overall_start

    # Print summary in original site order.
    results = [by_site[s] for s in sites if s in by_site]
    failed = [r for r in results if r[1] != 0]

    print()
    print("=" * 68)
    print(f"{'Site':<14}{'Status':<14}{'Time':>8}  Log")
    print("-" * 68)
    for site, rc, elapsed, log in results:
        status = "ok" if rc == 0 else f"FAIL rc={rc}"
        print(
            f"{site:<14}{status:<14}{elapsed:>6.1f}s  "
            f"{log.relative_to(REPO_ROOT)}"
        )
    print("-" * 68)
    print(
        f"Total: {overall_elapsed:.1f}s wall, "
        f"{len(results) - len(failed)} ok / {len(failed)} failed"
    )

    return min(len(failed), 255)


if __name__ == "__main__":
    sys.exit(main())
