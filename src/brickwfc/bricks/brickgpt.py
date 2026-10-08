"""Target shapes from BrickGPT's published structures (M12b step 1a).

StableText2Brick (Hugging Face ``AvaLovelace/StableText2Brick``, MIT per its dataset card) holds the
brick structures BrickGPT was trained on: ShapeNetCore objects, legolized in a 20 x 20 x 20 grid of
1 x 1 x 1-brick units (z up), captioned by GPT-4o. Each structure is one brick per line, ``"hxw (x,y,z)"``:
a brick ``h`` units along x and ``w`` along y, its min corner at ``(x, y, z)``, all bricks one unit tall.
Every brick size they use (1x1, 1x2, 1x4, 1x6, 1x8, 2x2, 2x4, 2x6) is a catalog brick, so a structure
converts exactly into our parts and our physics and cluster numbers apply to it unchanged.

Rows are fetched as JSON from the Hugging Face datasets-server API and cached in ``data/brickgpt/``
(third-party data, kept out of the repository like the OMR models). The cache keeps each row's
identifiers, captions and bricks, and BrickGPT's own stability score per brick (the dataset stores one
score per grid unit, indexed [x][y][z], 1 where empty; a brick gets the lowest score of its units).

Our cells are 1 stud x 1 stud x 1 plate and a brick is 3 plates tall, so a structure covers
(60, 20, 20) cells (Y, Z, X), with their x along our x and their y along our z.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np

from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.parts import CATALOG, Part, PlacedPart, Shape

DATASET = "AvaLovelace/StableText2Brick"
ROWS_URL = ("https://datasets-server.huggingface.co/rows?dataset={dataset}&config=default&split={split}"
            "&offset={offset}&length={length}")
DATA_DIR = Path("data/brickgpt")
GRID = 20  # units per side
UNIT_PLATES = 3  # a unit is one brick tall
PAGE = 100  # the API's maximum rows per request

_LINE = re.compile(r"^\s*(\d+)x(\d+)\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)\s*$")


@dataclass(frozen=True)
class Brick:
    h: int  # units along x
    w: int  # units along y
    x: int
    y: int
    z: int  # layer (up)

    def units(self) -> Iterator[tuple[int, int, int]]:
        """(x, y, z) of each unit the brick covers."""
        for dx in range(self.h):
            for dy in range(self.w):
                yield self.x + dx, self.y + dy, self.z


@dataclass(frozen=True)
class Structure:
    structure_id: str
    object_id: str
    category_id: str
    captions: tuple[str, ...]
    bricks: tuple[Brick, ...]
    scores: tuple[float, ...]  # BrickGPT's stability score per brick (empty for a local file)


def parse(text: str) -> list[Brick]:
    """Bricks of a structure in BrickGPT's text format (blank lines ignored)."""
    bricks = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = _LINE.match(line)
        if match is None:
            raise ValueError(f"line {number}: expected 'hxw (x,y,z)', got {line!r}")
        bricks.append(Brick(*(int(v) for v in match.groups())))
    return bricks


def overlaps(bricks: Sequence[Brick]) -> int:
    """Units covered by more than one brick (0 for a well-formed structure)."""
    seen: dict[tuple[int, int, int], int] = {}
    for brick in bricks:
        for unit in brick.units():
            seen[unit] = seen.get(unit, 0) + 1
    return sum(n - 1 for n in seen.values() if n > 1)


def occupancy(bricks: Sequence[Brick]) -> np.ndarray:
    """(Y, Z, X) cells of the structure: (UNIT_PLATES x the height, the y extent, the x extent), at least
    the 20-unit grid."""
    ny = max([GRID, *(b.z + 1 for b in bricks)]) * UNIT_PLATES
    nz = max([GRID, *(b.y + b.w for b in bricks)])
    nx = max([GRID, *(b.x + b.h for b in bricks)])
    mask = np.zeros((ny, nz, nx), dtype=bool)
    for b in bricks:
        mask[b.z * UNIT_PLATES : (b.z + 1) * UNIT_PLATES, b.y : b.y + b.w, b.x : b.x + b.h] = True
    return mask


def _brick_parts() -> dict[tuple[int, int], Part]:
    """Catalog bricks by (depth, width) footprint."""
    return {(p.depth, p.width): p for p in CATALOG.values() if p.kind == "brick" and "_" not in p.name}


def to_placed(bricks: Sequence[Brick], color: BrickColor) -> list[PlacedPart]:
    """The structure as catalog bricks, one per BrickGPT brick, all in ``color``."""
    by_size = _brick_parts()
    placed = []
    for b in bricks:
        part = by_size.get((min(b.h, b.w), max(b.h, b.w)))
        if part is None:
            raise ValueError(f"no catalog brick of {b.h}x{b.w} studs")
        # A part is ``width`` long along x unless rotated.
        shape = Shape(part, b.h != part.width)
        placed.append(PlacedPart(shape, color, b.z * UNIT_PLATES, b.x, b.y))
    return placed


# Fetching and caching ---------------------------------------------------------------------------------


def _get_json(url: str, retries: int = 8, timeout_s: float = 60) -> dict:
    """GET ``url`` as JSON, retrying with exponential backoff (rate limits: at least the server's
    Retry-After)."""
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "brickwfc"})
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == retries - 1:
                raise
            wait = 2.0 ** (attempt + 1)
            if isinstance(error, urllib.error.HTTPError) and error.headers.get("Retry-After", "").isdigit():
                wait = max(wait, float(error.headers["Retry-After"]))
            time.sleep(wait)
    raise AssertionError("unreachable")


def _compact(row: dict) -> dict:
    """A dataset row as cached: identifiers, captions, bricks and the score of each brick."""
    bricks = parse(row["bricks"])
    grid = row["stability_scores"]  # [x][y][z]
    return {
        "structure_id": row["structure_id"], "object_id": row["object_id"], "category_id": row["category_id"],
        "captions": row["captions"], "bricks": row["bricks"],
        "scores": [min(grid[x][y][z] for x, y, z in b.units()) for b in bricks],
    }


def cache_path(split: str, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / f"{split}.jsonl"


def fetch_rows(split: str = "test", data_dir: Path = DATA_DIR, page: int = PAGE) -> Path:
    """Download every row of ``split`` into ``data_dir/<split>.jsonl`` (one compact row per line).
    Resumable: rows already cached are not fetched again."""
    path = cache_path(split, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = sum(1 for line in path.open(encoding="utf-8") if line.strip()) if path.exists() else 0
    total = None
    while total is None or done < total:
        url = ROWS_URL.format(dataset=DATASET.replace("/", "%2F"), split=split, offset=done, length=page)
        data = _get_json(url)
        total = data["num_rows_total"]
        rows = sorted(data["rows"], key=lambda r: r["row_idx"])
        if not rows:
            break
        if rows[0]["row_idx"] != done:
            raise RuntimeError(f"{split}: expected row {done}, got {rows[0]['row_idx']}")
        with path.open("a", encoding="utf-8") as out:
            for r in rows:
                out.write(json.dumps(_compact(r["row"])) + "\n")
        done += len(rows)
    return path


def from_json(data: dict) -> Structure:
    return Structure(data["structure_id"], data["object_id"], data["category_id"], tuple(data["captions"]),
                     tuple(parse(data["bricks"])), tuple(data["scores"]))


def load_split(split: str = "test", data_dir: Path = DATA_DIR) -> list[Structure]:
    """Every structure of ``split``, fetched first if not cached."""
    path = fetch_rows(split, data_dir)
    return [from_json(json.loads(line)) for line in path.open(encoding="utf-8") if line.strip()]


def find(structure_id: str, data_dir: Path = DATA_DIR, splits: Sequence[str] = ("test",)) -> Structure:
    """The structure with this id (a unique prefix works) in the cached ``splits``."""
    for split in splits:
        found = [s for s in load_split(split, data_dir) if s.structure_id.startswith(structure_id)]
        if len(found) > 1:
            raise ValueError(f"brickgpt:{structure_id} matches {len(found)} structures; give more of the id")
        if found:
            return found[0]
    raise ValueError(f"brickgpt:{structure_id}: no such structure in the {'/'.join(splits)} split")
