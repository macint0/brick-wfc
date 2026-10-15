"""Crawl the whole LDraw Official Model Repository (OMR) into ``data/omr`` (M12e).

    python -m brickwfc.ldraw.omr_crawl --out data/omr

The OMR has no JSON API; its index is the paginated sets table at ``library.ldraw.org/omr/sets?page=N``
(25 sets per page: set number, name, theme, year, model count, and a link to the set's page). Each set page
lists the set's models (main model and official alternates, marked ``main`` in the index), each with its author, its missing-parts flags
and a download link ``library.ldraw.org/library/omr/<file>.mpd``. The crawl reads every index page, every
set page, then downloads every model file.

Polite and resumable: one request at a time with ``--delay`` seconds between requests, a User-Agent that
names the project, retries with backoff on transient errors (HTTP 429 / 5xx, timeouts, dropped
connections; ``Retry-After`` honoured). A model file that exists is not downloaded again; the parsed set
pages are kept in ``index.jsonl`` (one line per set, appended as they are read), so a rerun skips the sets it
has already read; ``--refresh`` reads the index pages and set pages again. ``index.json`` is the merged
index: every set with its models and their local files. OMR models are third-party work (author and license
in each file's header): they stay in ``data/`` (gitignored) and are never committed.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Sequence

BASE = "https://library.ldraw.org"
SETS_URL = BASE + "/omr/sets?page={page}"
SET_URL = BASE + "/omr/sets/{id}"
USER_AGENT = "brickwfc-research/0.1 (alternate-build research crawler; one request at a time)"
TRANSIENT = {408, 425, 429, 500, 502, 503, 504}

Get = Callable[[str], bytes]


@dataclass
class OmrModel:
    """One model of a set: its display name, author, the OMR file name and the missing-parts flags."""

    name: str
    author: str
    file: str  # e.g. 10019-1.mpd or 8094-1_Robotic-Arm.mpd
    missing_parts: bool | None = None
    missing_patterns: bool | None = None
    missing_stickers: bool | None = None
    main: bool | None = None  # the set's main model; False for an official alternate (``mark_main``)

    @property
    def url(self) -> str:
        return f"{BASE}/library/omr/{self.file}"


@dataclass
class OmrSet:
    """One row of the OMR sets table, with the set page's models once read."""

    id: int  # the OMR's record id (``/omr/sets/<id>``), not the set number
    number: str
    name: str
    theme: str
    year: int | None
    models_count: int
    models: list[OmrModel] = field(default_factory=list)

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, row: dict) -> "OmrSet":
        return cls(**{**row, "models": [OmrModel(**m) for m in row.get("models", [])]})


def mark_main(row: OmrSet) -> OmrSet:
    """Drop repeated models (a few set pages list a model twice) and mark each model main or alternate: the main model is ``<set number>.mpd``, or the first model listed when
    no file has that name (sets whose models are all named alternates, such as 8094-1). Alternates share the main
    model's inventory, so splits must keep them with their set."""
    unique: dict[str, OmrModel] = {}
    for m in row.models:
        unique.setdefault(m.file, m)
    row.models = list(unique.values())
    main = next((m.file for m in row.models if m.file == f"{row.number}.mpd"),
                row.models[0].file if row.models else None)
    for m in row.models:
        m.main = m.file == main
    return row


# Parsing ------------------------------------------------------------------------------------------------


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


_CELL = re.compile(r'table\.record\.(\d+)\.column\.([\w.]+)"[^>]*>(.*?)</td>', re.S)
_PAGE = re.compile(r"gotoPage\((\d+),")


def parse_sets_page(page: str) -> tuple[list[OmrSet], int]:
    """(the sets on one index page in table order, the highest page number the pager links to)."""
    rows: dict[int, dict[str, str]] = {}
    for record, column, inner in _CELL.findall(page):
        rows.setdefault(int(record), {})[column] = _text(inner)
    sets = []
    for record, cells in rows.items():
        year = cells.get("year", "")
        count = cells.get("models_count", "")
        sets.append(OmrSet(record, cells.get("number", ""), cells.get("name", ""), cells.get("theme.name", ""),
                           int(year) if year.isdigit() else None, int(count) if count.isdigit() else 0))
    last = max((int(n) for n in _PAGE.findall(page)), default=1)
    return sets, last


_MODEL = re.compile(r'<div class="font-bold bg-gray-200 p-2">(.*?)</div>(.*?)href="[^"]*/library/omr/([^"]+?\.mpd)"', re.S)
_AUTHOR = re.compile(r"Author:</span>(.*?)</div>", re.S)


def _flag(block: str, label: str) -> bool | None:
    match = re.search(label + r"</span>\s*<br>\s*(\w+)", block)
    return None if match is None else match.group(1).lower() == "yes"


def parse_set_page(page: str) -> list[OmrModel]:
    """The models listed on a set page, in page order."""
    models = []
    for name, block, file in _MODEL.findall(page):
        author = _AUTHOR.search(block)
        models.append(OmrModel(_text(name), _text(author.group(1)) if author else "", html.unescape(file),
                               _flag(block, "Missing Parts"), _flag(block, "Missing Patterns"),
                               _flag(block, "Missing Stickers")))
    return models


# HTTP ---------------------------------------------------------------------------------------------------


class PoliteClient:
    """Sequential GETs with a fixed gap between requests and retries on transient errors."""

    def __init__(self, delay_s: float = 1.0, retries: int = 4, timeout_s: float = 60,
                 sleep: Callable[[float], None] = time.sleep, opener: Callable = urllib.request.urlopen) -> None:
        self.delay_s, self.retries, self.timeout_s = delay_s, retries, timeout_s
        self.sleep, self.opener = sleep, opener
        self.requests = 0
        self._last = 0.0

    def get(self, url: str) -> bytes:
        for attempt in range(self.retries + 1):
            wait = self.delay_s - (time.monotonic() - self._last)
            if wait > 0:
                self.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with self.opener(request, timeout=self.timeout_s) as response:
                    return response.read()
            except urllib.error.HTTPError as error:
                if error.code not in TRANSIENT or attempt == self.retries:
                    raise
                retry_after = error.headers.get("Retry-After", "") if error.headers else ""
                self.sleep(float(retry_after) if retry_after.isdigit() else self.backoff(attempt))
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == self.retries:
                    raise
                self.sleep(self.backoff(attempt))
        raise AssertionError("unreachable")

    def backoff(self, attempt: int) -> float:
        return min(120.0, 5.0 * 2**attempt)


# Crawl --------------------------------------------------------------------------------------------------


def read_index(get: Get, log: Callable[[str], None] = print) -> list[OmrSet]:
    """Every set in the OMR sets table, in table order (pages 1..last)."""
    sets, last = parse_sets_page(get(SETS_URL.format(page=1)).decode("utf-8", errors="replace"))
    page = 2
    while page <= last:
        rows, last_seen = parse_sets_page(get(SETS_URL.format(page=page)).decode("utf-8", errors="replace"))
        sets += rows
        last = max(last, last_seen)
        log(f"index page {page}/{last}: {len(sets)} sets")
        page += 1
    return sets


def load_jsonl(path: Path) -> dict[int, OmrSet]:
    """Set pages already read (the last line for a set wins)."""
    if not path.exists():
        return {}
    rows = [OmrSet.from_json(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {s.id: s for s in rows}


def crawl(out: Path, get: Get, refresh: bool = False, download: bool = True,
          log: Callable[[str], None] = print) -> tuple[list[OmrSet], dict[str, int]]:
    """Read the index and every set page (resumable through ``index.jsonl``), write ``index.json``, and download
    every model file not on disk. Returns the sets and counts (sets, models, on disk, downloaded, failed)."""
    out.mkdir(parents=True, exist_ok=True)
    sets_path, pages_path = out / "index_sets.json", out / "index.jsonl"
    if refresh or not sets_path.exists():
        rows = read_index(get, log)
        sets_path.write_text(json.dumps([s.to_json() for s in rows], indent=1), encoding="utf-8")
        if refresh and pages_path.exists():
            pages_path.unlink()
    rows = [OmrSet.from_json(r) for r in json.loads(sets_path.read_text(encoding="utf-8"))]
    done = load_jsonl(pages_path)
    with pages_path.open("a", encoding="utf-8") as f:
        for k, row in enumerate(rows):
            if row.id in done:
                continue
            row.models = parse_set_page(get(SET_URL.format(id=row.id)).decode("utf-8", errors="replace"))
            mark_main(row)
            f.write(json.dumps(row.to_json()) + "\n")
            f.flush()
            done[row.id] = row
            if k % 25 == 0:
                log(f"set pages: {len(done)}/{len(rows)}")
    merged = [mark_main(done[r.id]) for r in rows]
    # Rewritten in index order with every model marked main or alternate (older lines lacked the mark).
    pages_path.with_suffix(".tmp").write_text("".join(json.dumps(r.to_json()) + "\n" for r in merged), encoding="utf-8")
    pages_path.with_suffix(".tmp").replace(pages_path)
    (out / "index.json").write_text(json.dumps([s.to_json() for s in merged], indent=1), encoding="utf-8")
    counts = {"sets": len(merged), "models": sum(len(s.models) for s in merged), "on_disk": 0, "downloaded": 0,
              "failed": 0}
    failures: list[str] = []
    for s in merged:
        for m in s.models:
            path = out / m.file
            if path.exists():
                counts["on_disk"] += 1
                continue
            if not download:
                continue
            try:
                data = get(m.url)
            except urllib.error.HTTPError as error:
                counts["failed"] += 1
                failures.append(f"{m.file}: HTTP {error.code}")
                continue
            path.with_suffix(".part").write_bytes(data)  # swapped in whole: a killed crawl leaves no truncated model
            path.with_suffix(".part").replace(path)
            counts["downloaded"] += 1
            counts["on_disk"] += 1
            if counts["downloaded"] % 25 == 0:
                log(f"models: {counts['on_disk']}/{counts['models']} on disk")
    if download:  # an index-only run fetches nothing, so it leaves the last download's failures in place
        (out / "crawl_failures.txt").write_text("\n".join(failures) + ("\n" if failures else ""), encoding="utf-8")
    return merged, counts


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.ldraw.omr_crawl", description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("data/omr"))
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--refresh", action="store_true", help="read the index and every set page again")
    parser.add_argument("--index-only", action="store_true", help="read the index and set pages, download nothing")
    args = parser.parse_args(argv)
    client = PoliteClient(args.delay, args.retries)
    started = time.time()
    sets, counts = crawl(args.out, client.get, args.refresh, not args.index_only, lambda s: print(s, flush=True))
    print(json.dumps({**counts, "requests": client.requests, "minutes": round((time.time() - started) / 60, 1)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
