"""Set inventories from Rebrickable's public bulk downloads (M12c): any set number, no LDraw model needed.

Rebrickable (https://rebrickable.com/downloads/) publishes its database as gzipped CSV files, free and
without an API key. ``fetch`` downloads the ones used here into ``data/rebrickable/`` (third-party data,
kept out of the repository like the OMR models; a file already there is not downloaded again):

- ``sets`` (set_num, name, year, ...), ``inventories`` (id, version, set_num),
- ``inventory_parts`` (inventory_id, part_num, color_id, quantity, is_spare, ...),
- ``colors`` (id, name, rgb, ...), ``part_relationships`` (rel_type, child_part_num, parent_part_num).

``inventory`` looks a set up (``"6372-1"``), takes its latest inventory version, skips spare parts and maps
each part and color onto ours:

- **parts**: ``part_num + ".dat"`` when that LDraw file is in ``parts.BY_FILE`` (Rebrickable part numbers are
  LDraw's for plain parts); otherwise a print (``P``) or mold variant (``M``) falls back to its parent part
  (following the chain); everything else is ignored and counted.
- **colors**: Rebrickable's color ids are LDraw's codes for the classic colors, but its CSV does not say so
  and its RGB values differ from LDraw's (they follow BrickLink), so ``LDRAW_CODES`` lists the ids whose
  Rebrickable name is LDraw's name for that code (LDConfig.ldr; written down by hand, not read from a file),
  including the one renumbered solid color (Olive Green: Rebrickable 326, LDraw 330). Transparent colors are
  listed where the numbering is the same (clear, red, green, yellow, dark blue) and where the 28 M10 sets'
  LDraw models confirm a renumbering (Trans-Orange, Trans-Neon Orange, Trans-Light Blue). Any other color maps to
  the nearest palette color by RGB, and the report flags it. ``experiments.rebrickable_check`` tests the table
  on the 28 M10 sets against their LDraw models.

Sub-sets (``inventory_sets``) and minifigures (``inventory_minifigs``) are not followed: minifigure parts are
never catalog parts, and sub-sets only matter for bundles. ``inventory_parts`` is large (~14 MB gzipped);
it is read once per lookup of a batch of sets (``inventories``) and each set's rows are cached as
``data/rebrickable/sets/<set>.json``.
"""

from __future__ import annotations

import csv
import gzip
import json
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from brickwfc.bricks.colors import PALETTE, BrickColor, color_for_code
from brickwfc.bricks.parts import BY_FILE, Part

URL = "https://cdn.rebrickable.com/media/downloads/{name}.csv.gz"
FILES = ("sets", "inventories", "inventory_parts", "colors", "part_relationships")
DATA_DIR = Path("data/rebrickable")
FALLBACK_RELATIONS = ("P", "M")  # print -> plain part, mold variant -> parent

# Rebrickable color id -> LDraw code where the names agree with LDConfig.ldr (identical ids except Olive Green).
LDRAW_CODES: dict[int, int] = {
    **{i: i for i in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 17, 18, 19, 20, 22, 23, 25, 26, 27, 28, 29, 31,
                      68, 69, 70, 71, 72, 73, 74, 77, 78, 84, 85, 86, 89, 92, 110, 115, 118, 120, 125, 151, 191, 212,
                      216, 226, 232, 272, 288, 308, 313, 320, 321, 322, 323, 335, 351, 366, 373, 378, 379, 450, 462,
                      484, 503)},
    **{i: i for i in (33, 34, 36, 46, 47)},  # Trans-Dark Blue, -Green, -Red, -Yellow, -Clear
    **{i: i for i in (80, 82, 135, 137, 142, 148, 179, 183, 297, 334)},  # metallic, pearl, chrome
    326: 330,  # Olive Green
    # Transparent colors numbered differently; confirmed on the M10 sets' LDraw models (results/m12c_rebrickable.md).
    182: 57,  # Trans-Orange
    57: 38,  # Trans-Neon Orange
    41: 43,  # Trans-Light Blue
}


# Fetching ------------------------------------------------------------------------------------------------


def fetch(data_dir: Path = DATA_DIR, names: Sequence[str] = FILES, refresh: bool = False, timeout_s: float = 120) -> list[Path]:
    """Download the CSV files not already in ``data_dir`` (all of them with ``refresh``). A file is written to
    ``.part`` first and renamed when complete, so an interrupted download is not mistaken for a file.
    HTTP errors are raised with the URL."""
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        path = data_dir / f"{name}.csv.gz"
        if refresh or not path.exists():
            url = URL.format(name=name)
            partial = path.with_suffix(".gz.part")
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "brickwfc"})
                with urllib.request.urlopen(request, timeout=timeout_s) as response:
                    partial.write_bytes(response.read())
            except urllib.error.HTTPError as error:
                raise RuntimeError(f"{url}: HTTP {error.code} {error.reason}") from error
            partial.replace(path)
        paths.append(path)
    return paths


def rows(path: Path) -> Iterable[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


# Mapping ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RBColor:
    id: int
    name: str
    rgb: tuple[int, int, int]


def nearest_palette(rgb: tuple[int, int, int]) -> BrickColor:
    return min(PALETTE.values(), key=lambda c: sum((a - b) ** 2 for a, b in zip(c.rgb, rgb)))


def map_color(color: RBColor) -> tuple[BrickColor, bool]:
    """(our color, whether it was guessed by nearest RGB)."""
    if color.id in LDRAW_CODES:
        return color_for_code(LDRAW_CODES[color.id]), False
    return nearest_palette(color.rgb), True


def map_part(part_num: str, parents: Mapping[str, str], known: Mapping[str, Part] = BY_FILE) -> tuple[Part | None, str | None]:
    """(catalog part, the part number it was found under) for a Rebrickable part number, following print and
    mold relationships to the parent part; (None, None) if neither it nor a parent is in the catalog."""
    seen: set[str] = set()
    current: str | None = part_num
    while current is not None and current not in seen:
        part = known.get(f"{current.lower()}.dat")
        if part is not None:
            return part, current
        seen.add(current)
        current = parents.get(current)
    return None, None


# The database ------------------------------------------------------------------------------------------


@dataclass
class Report:
    set_num: str
    name: str
    year: int
    inventory_version: int
    parts: int = 0  # non-spare parts in the inventory
    recognized: int = 0
    via_parent: Counter = field(default_factory=Counter)  # Rebrickable part num -> parts mapped through a parent
    ignored: Counter = field(default_factory=Counter)  # Rebrickable part num -> parts not in the catalog
    guessed_colors: Counter = field(default_factory=Counter)  # "Rebrickable name -> our color" -> parts

    def to_json(self) -> dict:
        return {"set": self.set_num, "name": self.name, "year": self.year, "inventory_version": self.inventory_version,
                "parts": self.parts, "recognized": self.recognized, "via_parent": dict(self.via_parent),
                "ignored_top": self.ignored.most_common(10), "ignored": sum(self.ignored.values()),
                "guessed_colors": dict(self.guessed_colors)}


class Rebrickable:
    """The downloaded CSVs (fetched on first use); small tables in memory, inventory parts read per batch."""

    def __init__(self, data_dir: Path = DATA_DIR, download: bool = True) -> None:
        self.data_dir = data_dir
        if download:
            fetch(data_dir)
        self.sets = {r["set_num"]: r for r in rows(data_dir / "sets.csv.gz")}
        latest: dict[str, tuple[int, int]] = {}
        for r in rows(data_dir / "inventories.csv.gz"):
            version, ident = int(r["version"]), int(r["id"])
            if r["set_num"] not in latest or version > latest[r["set_num"]][0]:
                latest[r["set_num"]] = (version, ident)
        self.latest = latest
        self.colors = {int(r["id"]): RBColor(int(r["id"]), r["name"], tuple(int(r["rgb"][i : i + 2], 16) for i in (0, 2, 4)))
                       for r in rows(data_dir / "colors.csv.gz")}
        self.parents = {r["child_part_num"]: r["parent_part_num"] for r in rows(data_dir / "part_relationships.csv.gz")
                        if r["rel_type"] in FALLBACK_RELATIONS}

    def cache_path(self, set_num: str) -> Path:
        return self.data_dir / "sets" / f"{set_num}.json"

    def inventory_rows(self, set_nums: Sequence[str]) -> dict[str, list[dict]]:
        """Non-spare inventory rows of each set's latest inventory: cached per set, the big file read once for
        all the sets not cached yet."""
        found: dict[str, list[dict]] = {}
        wanted: dict[int, str] = {}
        for s in set_nums:
            if s not in self.latest:
                raise KeyError(f"{s}: no such set (or no inventory) in Rebrickable's data")
            path = self.cache_path(s)
            if path.exists():
                found[s] = json.loads(path.read_text(encoding="utf-8"))
            else:
                wanted[self.latest[s][1]] = s
        if wanted:
            collected: dict[str, list[dict]] = {s: [] for s in wanted.values()}
            for r in rows(self.data_dir / "inventory_parts.csv.gz"):
                s = wanted.get(int(r["inventory_id"]))
                if s is not None and r["is_spare"].lower() != "true":
                    collected[s].append({"part_num": r["part_num"], "color_id": int(r["color_id"]), "quantity": int(r["quantity"])})
            for s, found_rows in collected.items():
                self.cache_path(s).parent.mkdir(parents=True, exist_ok=True)
                self.cache_path(s).write_text(json.dumps(found_rows), encoding="utf-8")
                found[s] = found_rows
        return found

    def inventory(self, set_num: str, known: Mapping[str, Part] = BY_FILE) -> tuple[dict[tuple[str, str], int], Counter, list[BrickColor], Report]:
        """``(inventory, ignored part counts, colors, report)`` like ``inventory.inventory_from_mpd``; ignored parts
        are keyed by Rebrickable part number."""
        return self.inventories([set_num], known)[set_num]

    def inventories(self, set_nums: Sequence[str], known: Mapping[str, Part] = BY_FILE) -> dict[str, tuple]:
        result = {}
        for s, found_rows in self.inventory_rows(set_nums).items():
            info = self.sets.get(s, {})
            report = Report(s, info.get("name", ""), int(info.get("year", 0) or 0), self.latest[s][0])
            inventory: Counter = Counter()
            colors: dict[str, BrickColor] = {}
            for r in found_rows:
                count = r["quantity"]
                report.parts += count
                part, found_as = map_part(r["part_num"], self.parents, known)
                if part is None:
                    report.ignored[r["part_num"]] += count
                    continue
                if found_as != r["part_num"]:
                    report.via_parent[f"{r['part_num']} -> {found_as}"] += count
                rb_color = self.colors.get(r["color_id"], RBColor(r["color_id"], f"#{r['color_id']}", (128, 128, 128)))
                color, guessed = map_color(rb_color)
                if guessed:
                    report.guessed_colors[f"{rb_color.name} -> {color.name}"] += count
                colors[color.name] = color
                inventory[(part.name, color.name)] += count
                report.recognized += count
            result[s] = (dict(inventory), report.ignored, sorted(colors.values(), key=lambda c: c.ldraw), report)
        return result
