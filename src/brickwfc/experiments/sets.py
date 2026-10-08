"""Choose the real sets to learn style from (M10): building-type sets the catalog covers well.

    python -m brickwfc.experiments.sets --out out/sets

``CANDIDATES`` lists every building-type set in the LDraw OMR from the Town, City, Creator, Modular
Buildings, Legoland, Town Plan and Universal Building Set themes: everything in the building-only
sub-themes, plus sets elsewhere whose names say building (house, shop, station, ...) and not vehicle.
Built from the OMR set index on 2026-10-08. For each candidate this fetches its model (cached in
``data/``), measures the share of its parts in ``parts.CATALOG`` (``experiments.coverage``), drops
re-releases (identical recognized inventory; the earliest is kept), and selects sets with at least
``--min-share`` percent recognized, ``--min-parts`` parts, and ``--min-on-grid`` percent of the
recognized parts on the stud grid (the parts style statistics are learned from). Sets whose model is not at the default
OMR file name are reported as unavailable. For each set it also reports how many recognized parts
voxelize onto the stud grid (``bricks.voxelize``): those are what style statistics are learned from.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
from pathlib import Path
from typing import Sequence

from brickwfc.bricks.inventory import inventory_from_mpd
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.coverage import set_coverage
from brickwfc.ldraw.mpd import flatten
from brickwfc.ldraw.fetch import fetch_set

# (set number, name, OMR theme, year), oldest first so that re-releases lose to the original.
CANDIDATES: list[tuple[str, str, str, int]] = [
    ("1210-2", "Small Store Set", "System > Town Plan", 1955),
    ("1211-2", "Small House Set", "System > Town Plan", 1955),
    ("1212-2", "Small House - Left Set", "System > Town Plan", 1955),
    ("1213-2", "Small House - Right Set", "System > Town Plan", 1955),
    ("349-1", "Swiss Chalet", "Legoland > Building", 1971),
    ("364-1", "Harbour Scene", "Legoland > Harbor", 1975),
    ("374-1", "Fire Station", "Town > Classic Town", 1978),
    ("376-2", "Town House with Garden", "Town > Classic Town", 1978),
    ("377-1", "Shell Service Station", "Town > Classic Town", 1978),
    ("361-2", "Garage", "Town > Classic Town", 1979),
    ("560-1", "Town House with Garden", "Town > Classic Town", 1979),
    ("6363-1", "Auto Service Station", "Town > Classic Town", 1980),
    ("722-1", "Universal Building Set", "Universal Building Set", 1980),
    ("733-1", "Universal Building Set", "Universal Building Set", 1980),
    ("744-1", "Universal Building Set", "Universal Building Set", 1980),
    ("544-1", "Basic Set", "Universal Building Set", 1981),
    ("555-2", "Basic Set", "Universal Building Set", 1981),
    ("566-1", "Basic Set", "Universal Building Set", 1981),
    ("6365-1", "Summer Cottage", "Town > Classic Town", 1981),
    ("6382-1", "Fire Station", "Town > Classic Town", 1981),
    ("6362-1", "Post Office", "Town > Classic Town", 1982),
    ("6372-1", "Town House", "Town > Classic Town", 1982),
    ("6374-1", "Holiday Home", "Town > Classic Town", 1983),
    ("6384-1", "Police Station", "Town > Classic Town", 1983),
    ("6683-1", "Burger Stand", "Town > Classic Town", 1983),
    ("6369-1", "Garage", "Town > Classic Town", 1985),
    ("6370-1", "Weekend Home", "Town > Classic Town", 1985),
    ("6392-1", "Airport", "Town > Classic Town", 1985),
    ("6689-1", "Post-Station", "Town > Classic Town", 1985),
    ("6360-1", "Weekend Cottage", "Town > Classic Town", 1986),
    ("6378-1", "Shell Service Station", "Town > Classic Town", 1986),
    ("6386-1", "Police Command Base", "Town > Classic Town", 1986),
    ("1472-1", "Holiday Home", "Town > Classic Town", 1987),
    ("1484-1", "Weetabix Town House", "Town > Classic Town", 1987),
    ("6380-1", "Emergency Treatment Center", "Town > Classic Town", 1987),
    ("6699-1", "Cycle Fix-It Shop", "Town > Classic Town", 1987),
    ("1490-1", "Town Bank", "Town > Classic Town", 1988),
    ("6349-1", "Vacation House", "Town > Classic Town", 1988),
    ("6376-1", "Breezeway Cafe", "Town > Classic Town", 1990),
    ("6389-1", "Fire Control Center", "Town > Classic Town", 1990),
    ("6540-1", "Pier Police", "Town > Classic Town", 1991),
    ("6416-1", "Poolside Paradise", "Town > Paradisa", 1992),
    ("6552-1", "Rocky River Retreat", "Town > Classic Town", 1993),
    ("6350-1", "Pizza To Go", "Town > Classic Town", 1994),
    ("6402-1", "Sidewalk Cafe", "Town > Paradisa", 1994),
    ("6414-1", "Dolphin Point", "Town > Paradisa", 1995),
    ("6562-1", "Gas Stop Shop", "Town > Classic Town", 1995),
    ("1854-1", "House with Roof-Windows (Velux)", "Town > Classic Town", 1996),
    ("6598-1", "Metro PD Station", "Town > Classic Town", 1996),
    ("6479-1", "Emergency Response Center", "Town > Res-Q", 1998),
    ("10036-1", "Pizza To Go", "Town", 2002),
    ("10037-1", "Breezeway Cafe", "Town", 2002),
    ("10159-1", "City Airport", "City > Airport", 2004),
    ("4886-1", "Building Bonanza", "Creator > Designer Sets", 2004),
    ("10182-1", "Cafe Corner", "Modular Buildings", 2007),
    ("10190-1", "Market Street", "Modular Buildings", 2007),
    ("4954-1", "Model Town House", "Creator > Creator 3-in-1", 2007),
    ("4956-1", "House", "Creator > Creator 3-in-1", 2007),
    ("7997-1", "Train Station", "City > Trains", 2007),
    ("10184-1", "Town Plan", "Town > Town Plan", 2008),
    ("10185-1", "Green Grocer", "Modular Buildings", 2008),
    ("4996-1", "Beach House", "Creator > Creator 3-in-1", 2008),
    ("7743-1", "Police Command Center", "City > Police", 2008),
    ("7796-1", "House", "Creator", 2008),
    ("10197-1", "Fire Brigade", "Modular Buildings", 2009),
    ("7637-1", "Farm", "City > Farm", 2009),
    ("7641-1", "City Corner", "City > Traffic", 2009),
    ("5891-1", "Apple Tree House", "Creator > Creator 3-in-1", 2010),
    ("10218-1", "Pet Shop", "Modular Buildings", 2011),
    ("30023-1", "Lighthouse", "Creator", 2011),
    ("5766-1", "Log Cabin", "Creator > Creator 3-in-1", 2011),
    ("5770-1", "Lighthouse Island", "Creator > Creator 3-in-1", 2011),
    ("5771-1", "Hillside House", "Creator > Creator 3-in-1", 2011),
    ("10224-1", "Town Hall", "Modular Buildings", 2012),
    ("10232-1", "Palace Cinema", "Modular Buildings", 2013),
    ("31009-1", "Small Cottage", "Creator > Creator 3-in-1", 2013),
    ("10243-1", "Parisian Restaurant", "Modular Buildings", 2014),
    ("10246-1", "Detective's Office", "Modular Buildings", 2015),
    ("10251-1", "Brick Bank", "Modular Buildings", 2016),
    ("31048-1", "Lakeside Lodge", "Creator > Creator 3-in-1", 2016),
    ("10264-1", "Corner Garage", "Modular Buildings", 2019),
    ("60216-1", "Downtown Fire Brigade", "City > Fire", 2019),
    ("10270-1", "Bookshop", "Modular Buildings", 2020),
    ("10278-1", "Police Station", "Modular Buildings", 2021),
    ("10297-1", "Boutique Hotel", "Modular Buildings", 2022),
    ("31153-1", "Modern House", "Creator > Creator 3-in-1", 2024),
]


def evaluate(data: Path) -> list[dict]:
    """One row per candidate: recognized share, part count, and why it was not selected (if so)."""
    rows: list[dict] = []
    seen: dict[tuple, str] = {}
    for number, name, theme, year in CANDIDATES:
        row = {"set": number, "name": name, "theme": theme, "year": year}
        try:
            text = fetch_set(number, data).read_text(encoding="utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            rows.append({**row, "parts": 0, "catalog_pct": 0.0, "catalog": 0, "on_grid": 0, "tilted": 0, "off_grid": 0,
                         "overlapping": 0, "note": f"unavailable (HTTP {error.code})"})
            continue
        coverage = set_coverage(number, text)
        inventory, _, _ = inventory_from_mpd(text)
        key = tuple(sorted(inventory.items()))
        note = f"re-release of {seen[key]}" if key in seen and inventory else ""
        seen.setdefault(key, number)
        _, report = voxelize(flatten(text))
        rows.append({**row, "parts": coverage.parts, "catalog_pct": coverage.catalog_pct, "catalog": coverage.catalog,
                     "on_grid": report.kept, "tilted": report.tilted, "off_grid": report.off_grid,
                     "overlapping": report.overlapping, "note": note})
    return rows


def on_grid_pct(row: dict) -> float:
    return 100 * row["on_grid"] / row["catalog"] if row["catalog"] else 0.0


def select(rows: list[dict], min_share: float, min_parts: int, min_on_grid: float = 0.0) -> list[dict]:
    return [r for r in rows if reason(r, min_share, min_parts, min_on_grid) == "yes"]


def reason(row: dict, min_share: float, min_parts: int, min_on_grid: float = 0.0) -> str:
    """"yes" for a selected candidate, otherwise why it was not selected."""
    if row["note"]:
        return row["note"]
    if row["catalog_pct"] < min_share:
        return f"< {min_share:.0f}% recognized"
    if row["parts"] < min_parts:
        return f"< {min_parts} parts"
    if on_grid_pct(row) < min_on_grid:
        return f"< {min_on_grid:.0f}% on grid"
    return "yes"


def markdown(rows: list[dict], min_share: float, min_parts: int, min_on_grid: float = 0.0) -> str:
    lines = ["| set | name | theme | year | parts | recognized % | on grid | on grid % | tilted | off grid | overlapping "
             "| selected |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: -r["catalog_pct"]):
        mark = reason(r, min_share, min_parts, min_on_grid)
        on_grid = f"{100 * r['on_grid'] / r['catalog']:.0f}" if r["catalog"] else "—"
        lines.append(f"| {r['set']} | {r['name']} | {r['theme']} | {r['year']} | {r['parts']} | {r['catalog_pct']:.1f} | "
                     f"{r['on_grid']} | {on_grid} | {r['tilted']} | {r['off_grid']} | {r['overlapping']} | {mark} |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.sets", description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--min-share", type=float, default=50.0, help="minimum recognized-part share, percent")
    parser.add_argument("--min-parts", type=int, default=50)
    parser.add_argument("--min-on-grid", type=float, default=50.0, help="minimum percent of recognized parts on the grid")
    parser.add_argument("--out", type=Path, default=Path("out/sets"))
    args = parser.parse_args(argv)
    rows = evaluate(args.data)
    chosen = select(rows, args.min_share, args.min_parts, args.min_on_grid)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "sets.json").write_text(json.dumps({"candidates": rows, "selected": [r["set"] for r in chosen]}, indent=2),
                                        encoding="utf-8")
    table = markdown(rows, args.min_share, args.min_parts, args.min_on_grid)
    (args.out / "sets.md").write_text(table + "\n", encoding="utf-8")
    print(table)
    print(f"selected {len(chosen)} of {len(rows)} candidates: {' '.join(r['set'] for r in chosen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
