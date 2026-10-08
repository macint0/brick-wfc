"""How much of each set the generators can use: recognized-part share per set (M8).

    python -m brickwfc.experiments.coverage --out results/m8_coverage

For each set's OMR model, counts part instances (LDraw primitives such as ``4-4cyli.dat``, which only
appear inside custom parts defined in the file, are not parts and are left out) and how many are in
the four M4-M11 plates and in the full ``parts.CATALOG``. Writes ``coverage.md`` and ``coverage.json``.
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
from brickwfc.bricks.parts import BY_FILE, PLATE_FILES
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

    @property
    def plates4_pct(self) -> float:
        return 100 * self.plates4 / self.parts if self.parts else 0.0

    @property
    def catalog_pct(self) -> float:
        return 100 * self.catalog / self.parts if self.parts else 0.0


def set_coverage(set_number: str, text: str) -> SetCoverage:
    names = [inst.part.lower() for inst in flatten(text)]
    parts = [n for n in names if not PRIMITIVE.search(n)]
    missing = Counter(n for n in parts if n not in BY_FILE)
    return SetCoverage(
        set_number, len(parts), len(names) - len(parts), sum(n in PLATE_FILES for n in parts),
        sum(n in BY_FILE for n in parts), missing.most_common(5),
    )


def markdown(rows: list[SetCoverage]) -> str:
    lines = ["| set | parts | four plates % | catalog % | most common missing |", "|---|---|---|---|---|"]
    for r in rows:
        missing = ", ".join(f"{name.removesuffix('.dat')} ({n})" for name, n in r.top_missing[:3])
        lines.append(f"| {r.set_number} | {r.parts} | {r.plates4_pct:.0f} | {r.catalog_pct:.0f} | {missing} |")
    total = sum(r.parts for r in rows)
    if total:
        lines.append(f"| **all** | {total} | {100 * sum(r.plates4 for r in rows) / total:.0f} | "
                     f"{100 * sum(r.catalog for r in rows) / total:.0f} | |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.coverage", description=__doc__.splitlines()[0])
    parser.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS))
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--out", type=Path, default=Path("out/coverage"))
    args = parser.parse_args(argv)
    rows = [set_coverage(s, fetch_set(s, args.data).read_text(encoding="utf-8", errors="replace")) for s in args.sets]
    rows.sort(key=lambda r: -r.catalog_pct)
    args.out.mkdir(parents=True, exist_ok=True)
    table = markdown(rows)
    (args.out / "coverage.md").write_text(table + "\n", encoding="utf-8")
    (args.out / "coverage.json").write_text(
        json.dumps([{**asdict(r), "plates4_pct": r.plates4_pct, "catalog_pct": r.catalog_pct} for r in rows], indent=2),
        encoding="utf-8",
    )
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
