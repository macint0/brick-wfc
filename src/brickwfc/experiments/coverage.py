"""How much of each set the generators can use: recognized-part share per set (M8, M12b).

    python -m brickwfc.experiments.coverage --out results/m8_coverage
    python -m brickwfc.experiments.coverage --sets-file results/sets_selection.json --on-grid --out out/m12b_cov

For each set's OMR model, counts part instances (LDraw primitives such as ``4-4cyli.dat``, which only
appear inside custom parts defined in the file, are not parts and are left out) and how many are in
the four M4-M11 plates, in the M8 catalog (``parts.M8_FILES``: rectangular plates, bricks, tiles), in the
M12b catalog (``parts.M12B_FILES``: also corners and slopes) and in the full ``parts.CATALOG`` (M12d: the real
sets' parts). With ``--on-grid``, also how many voxelize
onto the stud grid (``bricks.voxelize``) with each catalog: those are what style statistics learn from.
``--sets-file`` takes the sets from an ``experiments.sets`` selection (its "selected" list) instead of
``--sets``. Writes ``coverage.md`` and ``coverage.json``.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from brickwfc.bricks.learn_sets import DEFAULT_SETS
from brickwfc.bricks.parts import BY_FILE, M8_FILES, M12B_FILES, PLATE_FILES
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten

PRIMITIVE = re.compile(r"^(\d+-\d+|stud)|[\\/]")  # 4-4cyli.dat, 1-4edge.dat, stud.dat, s\..., 48\...


@dataclass(frozen=True)
class SetCoverage:
    set_number: str
    parts: int
    primitives: int
    plates4: int  # instances among the four M4-M11 plates
    catalog: int  # instances in parts.CATALOG
    top_missing: list[tuple[str, int]]
    catalog_m8: int = 0  # instances in the M8 catalog
    on_grid: int = -1  # instances that voxelize onto the stud grid with parts.CATALOG (-1: not measured)
    on_grid_m8: int = -1  # the same with the M8 catalog
    catalog_m12b: int = 0  # instances in the M12b catalog (88 parts)
    on_grid_m12b: int = -1

    @property
    def plates4_pct(self) -> float:
        return 100 * self.plates4 / self.parts if self.parts else 0.0

    @property
    def catalog_pct(self) -> float:
        return 100 * self.catalog / self.parts if self.parts else 0.0

    @property
    def catalog_m8_pct(self) -> float:
        return 100 * self.catalog_m8 / self.parts if self.parts else 0.0


def set_coverage(set_number: str, text: str, on_grid: bool = False) -> SetCoverage:
    instances = flatten(text)
    names = [inst.part.lower() for inst in instances]
    parts = [n for n in names if not PRIMITIVE.search(n)]
    missing = Counter(n for n in parts if n not in BY_FILE)
    kept = kept_m8 = kept_m12b = -1
    if on_grid:
        from brickwfc.bricks.voxelize import voxelize

        kept, kept_m8, kept_m12b = (voxelize(instances, known)[1].kept for known in (BY_FILE, M8_FILES, M12B_FILES))
    return SetCoverage(
        set_number, len(parts), len(names) - len(parts), sum(n in PLATE_FILES for n in parts),
        sum(n in BY_FILE for n in parts), missing.most_common(5), sum(n in M8_FILES for n in parts), kept, kept_m8,
        sum(n in M12B_FILES for n in parts), kept_m12b,
    )


def markdown(rows: list[SetCoverage]) -> str:
    grid = bool(rows) and all(r.on_grid >= 0 for r in rows)
    columns = ["set", "parts", "four plates %", "M8 catalog %", "M12b catalog %", "catalog %"]
    columns += ["on grid M8 %", "on grid M12b %", "on grid %"] if grid else []
    columns += ["most common missing"]
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]

    def pct(n: int, total: int) -> str:
        return f"{100 * n / total:.0f}" if total else "0"

    for r in rows:
        missing = ", ".join(f"{name.removesuffix('.dat')} ({n})" for name, n in r.top_missing[:3])
        cells = [r.set_number, str(r.parts), pct(r.plates4, r.parts), pct(r.catalog_m8, r.parts),
                 pct(r.catalog_m12b, r.parts), pct(r.catalog, r.parts)]
        if grid:
            cells += [pct(r.on_grid_m8, r.parts), pct(r.on_grid_m12b, r.parts), pct(r.on_grid, r.parts)]
        lines.append("| " + " | ".join(cells + [missing]) + " |")
    total = sum(r.parts for r in rows)
    if total:
        fields = ["plates4", "catalog_m8", "catalog_m12b", "catalog"] + (["on_grid_m8", "on_grid_m12b", "on_grid"] if grid else [])
        cells = ["**all**", str(total)] + [pct(sum(getattr(r, f) for r in rows), total) for f in fields]
        lines.append("| " + " | ".join(cells + [""]) + " |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.coverage", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS))
    parser.add_argument("--sets-file", type=Path, help="an experiments.sets selection; its selected sets replace --sets")
    parser.add_argument("--on-grid", action="store_true", help="also count parts that voxelize onto the stud grid")
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--out", type=Path, default=Path("out/coverage"))
    args = parser.parse_args(argv)
    sets = json.loads(args.sets_file.read_text(encoding="utf-8"))["selected"] if args.sets_file else args.sets
    rows = [set_coverage(s, fetch_set(s, args.data).read_text(encoding="utf-8", errors="replace"), args.on_grid)
            for s in sets]
    rows.sort(key=lambda r: -r.catalog_pct)
    args.out.mkdir(parents=True, exist_ok=True)
    table = markdown(rows)
    (args.out / "coverage.md").write_text(table + "\n", encoding="utf-8")
    (args.out / "coverage.json").write_text(
        json.dumps([{**asdict(r), "plates4_pct": r.plates4_pct, "catalog_m8_pct": r.catalog_m8_pct,
                     "catalog_pct": r.catalog_pct} for r in rows], indent=2),
        encoding="utf-8",
    )
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
