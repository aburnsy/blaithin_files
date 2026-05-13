"""RHS plant detail scraper — API-driven, resumable, single parquet output.

The RHS Angular site fronts a JSON detail endpoint:

    GET https://lwapp-uks-prod-psearch-01.azurewebsites.net/api/v1/plants/details/{id}

We fetch every ID from ``data/rhs_urls.parquet`` through this endpoint,
stage results in a sqlite database at ``data/rhs/_staging.sqlite``, and
finalise the run by dumping a single ``data/rhs/data.parquet``.

Resuming is automatic: on startup we read ``SELECT id FROM plants`` and skip
those IDs. 404s land in a ``failed_ids`` table and stay there until a
``retry_failed=True`` run revisits them.

See ``docs/research/rhs-overhaul.md`` for the design rationale.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import re
import shutil
import sqlite3
import threading
from html import unescape
from pathlib import Path

import httpx
import polars as pl

from src.common.logging import get_logger
from src.scrapers.rhs_enums import (
    ASPECT,
    EXPOSURE,
    FOLIAGE,
    HABIT,
    HARDINESS,
    MOISTURE,
    PH,
    PLANT_TYPE,
    SOIL_TYPE,
    SUNLIGHT,
    decode_list,
    decode_scalar,
)

log = get_logger("scraper.rhs")

DETAIL_URL = "https://lwapp-uks-prod-psearch-01.azurewebsites.net/api/v1/plants/details/{id}"

DATA_DIR = Path("data") / "rhs"
STAGING_DB = DATA_DIR / "_staging.sqlite"
FINAL_PARQUET = DATA_DIR / "data.parquet"
FAILED_IDS_TXT = DATA_DIR / "failed_ids.txt"

_USER_AGENT = (
    "Mozilla/5.0 (compatible; blaithin-bot/1.0; +https://github.com/aburnsy/blaithin_files)"
)

_TAG_RE = re.compile(r"<[^>]+>")
_CULTIVAR_RE = re.compile(r"\s*'[^']+'\s*(\([^)]+\))?$")


class Fetch404(Exception):
    """The plant ID is not known to the detail API."""


class FetchFailed(Exception):
    """All retries exhausted on a non-404 error."""


def _strip_html(s: str | None) -> str | None:
    if not s:
        return None
    return _TAG_RE.sub("", unescape(s)).strip() or None


def _split_botanical(name: str | None) -> tuple[str, str]:
    """Return (genus, species) from a cleaned botanical name."""
    if not name:
        return "", ""
    cleaned = _CULTIVAR_RE.sub("", name).strip()
    # Drop the hybrid sign so the species token is the actual epithet
    cleaned = cleaned.replace("× ", "").replace(" ×", "")
    parts = cleaned.split(" ")
    genus = parts[0] if parts else ""
    species = parts[1] if len(parts) > 1 else ""
    return genus, species


def _build_plant_url(id_: int, botanical: str) -> str:
    """Mirror the slug the RHS site uses: dashes, no specials, URL-encoded."""
    import urllib.parse

    slug = botanical
    slug = (
        slug.replace(" ", "-")
        .replace("/", "-")
        .replace("-&-", "-")
        .replace("-+-", "-")
        .replace("+-", "-")
    )
    slug = slug.replace(".", "").replace("&", "").replace("'", "")
    slug = urllib.parse.quote(slug)
    return f"https://www.rhs.org.uk/plants/{id_}/{slug}/details"


def parse_detail(payload: dict) -> dict:
    """Pure function: API JSON -> column dict for the parquet row.

    No I/O; all decisions live here so the test suite can exercise the full
    parse without hitting the network.
    """
    id_ = int(payload["id"])

    botanical = payload.get("botanicalNameUnFormatted") or _strip_html(
        payload.get("botanicalName")
    ) or ""
    genus, species = _split_botanical(botanical)

    synonyms_raw = payload.get("synonyms") or []
    synonyms: list[str] = []
    for s in synonyms_raw:
        name = _strip_html(s.get("name") if isinstance(s, dict) else None)
        # The API often includes the plant itself in its own synonyms list;
        # filter that out.
        if name and (not isinstance(s, dict) or s.get("id") != id_):
            synonyms.append(name)

    common_name = payload.get("commonName") or None
    common_names = list(payload.get("commonNames") or [])
    # Keep both shapes populated; legacy fuzzy matcher reads singular,
    # RhsRecord target schema reads plural.
    if common_name and common_name not in common_names:
        common_names.insert(0, common_name)
    if not common_name and common_names:
        common_name = common_names[0]

    return {
        "rhs_id": id_,
        "plant_url": _build_plant_url(id_, botanical),
        "botanical_name": botanical,
        "genus": genus,
        "species": species,
        "family": payload.get("family") or None,
        "common_name": common_name,
        "common_names": common_names,
        "synonyms": synonyms,
        "plant_type": decode_list(payload.get("plantType"), PLANT_TYPE),
        "description": payload.get("entityDescription") or None,
        "is_rhs_award_winner": bool(payload.get("isAgm")),
        "is_pollinator_plant": bool(payload.get("isPlantsForPollinators")),
        "height": payload.get("height") or None,
        "spread": payload.get("spread") or None,
        "soils": decode_list(payload.get("soilType"), SOIL_TYPE),
        "moisture": _scalar_or_first(payload.get("moisture"), MOISTURE),
        "ph": decode_list(payload.get("ph"), PH),
        "sun_exposure": decode_list(payload.get("sunlight"), SUNLIGHT),
        "aspect": decode_list(payload.get("aspect"), ASPECT),
        "exposure": decode_list(payload.get("exposure"), EXPOSURE),
        "hardiness": decode_scalar(payload.get("hardinessLevel"), HARDINESS),
        "foliage": decode_list(payload.get("foliage"), FOLIAGE),
        "habit": decode_list(payload.get("habit"), HABIT),
        "source": "rhs",
    }


def _scalar_or_first(value, table: dict[int, str]) -> str | None:
    """RhsRecord declares ``moisture`` as ``str | None``; the API returns a list.

    Decode every value but only keep the first label so the column stays scalar.
    Returning the first matches the legacy scraper's output shape.
    """
    if value is None:
        return None
    if isinstance(value, list):
        decoded = decode_list(value, table)
        return decoded[0] if decoded else None
    return decode_scalar(int(value), table)


# ---------------------------------------------------------------------------
# Staging DB
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plants (
    id          INTEGER PRIMARY KEY,
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
    raw_json    TEXT NOT NULL,
    parsed_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS failed_ids (
    id        INTEGER PRIMARY KEY,
    reason    TEXT NOT NULL,
    attempts  INTEGER NOT NULL DEFAULT 1,
    last_seen TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _open_db(path: Path | None = None) -> sqlite3.Connection:
    if path is None:
        path = STAGING_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.executescript("PRAGMA journal_mode=WAL;\nPRAGMA synchronous=NORMAL;")
    conn.executescript(_SCHEMA)
    return conn


def _seen_ids(conn: sqlite3.Connection) -> set[int]:
    return {r[0] for r in conn.execute("SELECT id FROM plants")}


def _failed_id_set(conn: sqlite3.Connection) -> set[int]:
    return {r[0] for r in conn.execute("SELECT id FROM failed_ids")}


def _record_success(
    conn: sqlite3.Connection, lock: threading.Lock, id_: int, raw: dict, parsed: dict
) -> None:
    with lock:
        conn.execute(
            "INSERT OR REPLACE INTO plants(id, raw_json, parsed_json) VALUES (?, ?, ?)",
            (id_, json.dumps(raw, ensure_ascii=False), json.dumps(parsed, ensure_ascii=False)),
        )
        # If this ID was previously in failed_ids, clear it
        conn.execute("DELETE FROM failed_ids WHERE id = ?", (id_,))


def _record_failure(
    conn: sqlite3.Connection, lock: threading.Lock, id_: int, reason: str
) -> None:
    with lock:
        conn.execute(
            """INSERT INTO failed_ids(id, reason, attempts)
               VALUES (?, ?, 1)
               ON CONFLICT(id) DO UPDATE
                 SET reason=excluded.reason,
                     attempts=failed_ids.attempts + 1,
                     last_seen=datetime('now')""",
            (id_, reason),
        )


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _fetch_one(client: httpx.Client, id_: int, max_attempts: int = 3) -> dict:
    """Fetch a single plant's JSON. Raises Fetch404 or FetchFailed."""
    url = DETAIL_URL.format(id=id_)
    last_exc: Exception | None = None
    for _ in range(max_attempts):
        try:
            r = client.get(url)
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_exc = e
            continue
        if r.status_code == 404:
            raise Fetch404(f"id={id_} -> 404")
        if r.status_code >= 500 or r.status_code == 429:
            last_exc = httpx.HTTPStatusError(
                f"id={id_} -> {r.status_code}", request=r.request, response=r
            )
            continue
        if r.status_code != 200:
            raise FetchFailed(f"id={id_} -> {r.status_code}")
        try:
            return r.json()
        except json.JSONDecodeError as e:
            raise FetchFailed(f"id={id_} -> invalid JSON: {e}") from e
    raise FetchFailed(f"id={id_} -> {max_attempts} attempts: {last_exc}")


def _build_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        timeout=30.0,
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _remove_legacy_per_plant_files(data_dir: Path | None = None) -> int:
    """Delete the one-file-per-plant parquets the old scraper produced.

    Returns the number removed. Idempotent.
    """
    if data_dir is None:
        data_dir = DATA_DIR
    count = 0
    for p in data_dir.glob("*.parquet"):
        if p.name == FINAL_PARQUET.name:
            continue
        try:
            p.unlink()
            count += 1
        except OSError as e:
            log.warning("legacy_unlink_failed", path=str(p), error=str(e))
    return count


def _write_final_parquet(conn: sqlite3.Connection, out: Path | None = None) -> int:
    """Read parsed_json from sqlite and write the canonical parquet."""
    if out is None:
        out = FINAL_PARQUET
    rows: list[dict] = []
    for (parsed_json,) in conn.execute("SELECT parsed_json FROM plants"):
        rows.append(json.loads(parsed_json))
    if not rows:
        log.warning("no_rows_for_final_parquet")
        return 0
    df = pl.DataFrame(rows, infer_schema_length=None)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)
    return len(df)


def _dump_failed_ids(conn: sqlite3.Connection, out: Path | None = None) -> int:
    if out is None:
        out = FAILED_IDS_TXT
    rows = list(conn.execute("SELECT id, reason FROM failed_ids ORDER BY id"))
    if not rows:
        # Drop the file so a clean run has no stale failures hanging around
        if out.is_file():
            out.unlink()
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for id_, reason in rows:
            f.write(f"{id_}\t{reason}\n")
    return len(rows)


def get_plants_detail(
    plants: list[dict],
    *,
    max_workers: int = 12,
    retry_failed: bool = False,
    progress_every: int = 200,
) -> None:
    """Fetch plant detail for every entry in ``plants`` and write the parquet.

    ``plants`` matches the shape produced by ``rhs_urls.get_plant_urls()``:
    a list of dicts each carrying at least an ``id`` key. Other fields are
    ignored — the API is the source of truth for botanical/common names.

    Resumable: IDs already in the staging DB are skipped unless they appear in
    ``failed_ids`` AND ``retry_failed=True``.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    removed = _remove_legacy_per_plant_files()
    if removed:
        log.info("legacy_per_plant_files_removed", count=removed)

    conn = _open_db()
    db_lock = threading.Lock()

    seen = _seen_ids(conn)
    failed = _failed_id_set(conn)
    log.info("staging_state", seen=len(seen), failed=len(failed))

    all_ids = [int(p["id"]) for p in plants]
    to_fetch: list[int] = []
    for id_ in all_ids:
        if id_ in seen:
            continue
        if id_ in failed and not retry_failed:
            continue
        to_fetch.append(id_)

    total = len(to_fetch)
    log.info(
        "rhs_fetch_start",
        total_input=len(all_ids),
        already_done=len(seen),
        to_fetch=total,
        retry_failed=retry_failed,
        max_workers=max_workers,
    )

    if total == 0:
        log.info("rhs_nothing_to_fetch")
    else:
        fetched = 0
        errors_404 = 0
        errors_other = 0

        def _worker(id_: int) -> tuple[int, str]:
            try:
                payload = _fetch_one(client, id_)
            except Fetch404 as e:
                _record_failure(conn, db_lock, id_, "404")
                return id_, f"404: {e}"
            except FetchFailed as e:
                _record_failure(conn, db_lock, id_, type(e).__name__)
                return id_, f"FAIL: {e}"
            try:
                parsed = parse_detail(payload)
            except Exception as e:  # noqa: BLE001
                _record_failure(conn, db_lock, id_, f"parse_error: {e}")
                return id_, f"PARSE: {e}"
            _record_success(conn, db_lock, id_, payload, parsed)
            return id_, "ok"

        with _build_client() as client, cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_worker, id_) for id_ in to_fetch]
            for i, fut in enumerate(cf.as_completed(futures), start=1):
                _, status = fut.result()
                if status == "ok":
                    fetched += 1
                elif status.startswith("404"):
                    errors_404 += 1
                else:
                    errors_other += 1
                if i % progress_every == 0 or i == total:
                    log.info(
                        "rhs_progress",
                        done=i,
                        total=total,
                        fetched=fetched,
                        errors_404=errors_404,
                        errors_other=errors_other,
                    )

    written = _write_final_parquet(conn)
    failed_count = _dump_failed_ids(conn)
    log.info(
        "rhs_fetch_complete",
        rows_in_parquet=written,
        failed_ids=failed_count,
        parquet=str(FINAL_PARQUET),
        sidecar=str(FAILED_IDS_TXT) if failed_count else None,
    )
    conn.close()


# ---------------------------------------------------------------------------
# Maintenance: drop the staging DB if you want a clean slate.
# ---------------------------------------------------------------------------


def reset_staging() -> None:
    """Delete the staging sqlite and its WAL files. Used in tests."""
    for suffix in ("", "-wal", "-shm"):
        p = STAGING_DB.with_name(STAGING_DB.name + suffix)
        if p.is_file():
            p.unlink()
    if STAGING_DB.parent.is_dir():
        # Also wipe any straggler per-plant parquets
        _remove_legacy_per_plant_files()


# Convenience for "wipe everything and start fresh"; unused by load_bronze_data.
def clean_start() -> None:
    if DATA_DIR.is_dir():
        shutil.rmtree(DATA_DIR)
