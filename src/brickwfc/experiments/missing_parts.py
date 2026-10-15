"""Rank the parts the catalog cannot place, by instances across a set list (M12d).

    python -m brickwfc.experiments.missing_parts --sets-file results/sets_selection.json --out results/m12d_missing_parts.md
    python -m brickwfc.experiments.missing_parts --all --out out/missing_all.md

Counts part instances in the OMR models (``data/omr``) whose file is not in ``parts.BY_FILE``. LDraw primitives
and subparts (alphabetic names such as ``rect3``, ``n-m*`` such as ``4-4cyli``, ``stud*``, paths) are not parts and are
left out of every count. Names come from Rebrickable's ``parts.csv.gz`` when present ("?" otherwise: composite files
such as ``60593c01``, printed parts, obsolete numbers); the *kind* is a keyword heuristic on the name, for the
by-kind summary only. ``--all`` takes every ``.mpd`` in the data directory instead of a set list.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from brickwfc.bricks.parts import BY_FILE, Part
from brickwfc.ldraw.mpd import flatten

# LDraw primitives and subparts, not parts: 4-4cyli.dat, stud.dat, rect3.dat, box2-5.dat, s\3001s01.dat, 48\...
PRIMITIVE = re.compile(r"^(\d+-\d+|stud|[a-z])|[\\/]")

KINDS: tuple[tuple[str, str], ...] = (
    ("minifig", r"minifig|torso|legs|hair|helmet|cap |hat|hips|arm |hand"),
    ("technic", r"technic|axle|pin |gear|beam|liftarm"),
    ("wheel/vehicle", r"wheel|tyre|tire|steering|propeller|windscreen|wind screen"),
    ("window/door", r"window|door|shutter|glass|fence|gate|ladder"),
    ("jumper", r"plate 1 x 2 with 1 stud|jumper"),
    ("wedge plate", r"wedge.*plate|plate.*wedge|wedge, plate|plate 1 x 2 with angled|wing"),
    ("wedge brick", r"wedge"),
    ("curved slope", r"slope.*curved|curved|arch|bow"),
    ("round", r"round|cylinder|cone|dome|dish|disc"),
    ("bracket/snot", r"bracket|headlight|stud on side|studs on side|stud on 1 side|snot|erling"),
    ("hinge/clip/bar", r"hinge|clip|bar |handle|lever|turntable|ball|socket|antenna"),
    ("plate modified", r"plate.*(with|modified)"),
    ("brick modified", r"brick.*(with|modified|bow)"),
    ("tile modified", r"tile"),
    ("panel", r"panel|wall"),
    ("slope", r"slope"),
    ("plant/animal", r"plant|flower|leaf|tree|animal|horse"),
)


def kind_of(name: str) -> str:
    low = name.lower()
    return next((kind for kind, pattern in KINDS if re.search(pattern, low)), "other")


def part_names(parts_csv: Path) -> dict[str, str]:
    """Rebrickable part number (lower case) -> name; empty when the file is missing."""
    if not parts_csv.exists():
        return {}
    with gzip.open(parts_csv, "rt", encoding="utf-8") as handle:
        return {row["part_num"].lower(): row["name"] for row in csv.DictReader(handle)}


def name_of(file: str, names: Mapping[str, str]) -> str:
    """The Rebrickable name of an LDraw file: exact number first, then without its variant letters (3040b -> 3040)."""
    stem = file.removesuffix(".dat")
    for key in (stem, re.sub(r"[a-z]+$", "", stem)):
        if key in names:
            return names[key]
    return "?"


def model_parts(text: str) -> list[str]:
    """Lower-case part files of a model's instances, primitives and subparts left out."""
    return [inst.part.lower() for inst in flatten(text) if not PRIMITIVE.search(inst.part.lower())]


@dataclass(frozen=True)
class Ranking:
    total: int  # part instances
    recognized: int  # instances in the catalog
    missing: Counter  # file -> instances not in the catalog
    sets_with: Counter  # file -> number of models using it

    @property
    def recognized_pct(self) -> float:
        return 100 * self.recognized / self.total if self.total else 0.0


def rank(texts: Sequence[str], known: Mapping[str, Part] = BY_FILE) -> Ranking:
    missing: Counter = Counter()
    sets_with: defaultdict[str, set[int]] = defaultdict(set)
    total = recognized = 0
    for index, text in enumerate(texts):
        parts = model_parts(text)
        total += len(parts)
        for file in parts:
            if file in known:
                recognized += 1
            else:
                missing[file] += 1
                sets_with[file].add(index)
    return Ranking(total, recognized, missing, Counter({f: len(s) for f, s in sets_with.items()}))


def markdown(label: str, ranking: Ranking, names: Mapping[str, str], top: int) -> str:
    r = ranking
    lines = [f"## {label}: {r.total} parts, recognized {r.recognized} ({r.recognized_pct:.1f}%), "
             f"missing {r.total - r.recognized} in {len(r.missing)} distinct files", ""]
    by_kind: Counter = Counter()
    for file, n in r.missing.items():
        by_kind[kind_of(name_of(file, names))] += n
    lines += ["| kind | instances | % of all parts |", "|---|---|---|"]
    lines += [f"| {k} | {n} | {100 * n / r.total:.1f} |" for k, n in by_kind.most_common()]
    lines += ["", "| # | file | instances | sets | cum % of all parts | kind | name |", "|---|---|---|---|---|---|---|"]
    cumulative = r.recognized
    for i, (file, n) in enumerate(r.missing.most_common(top), 1):
        cumulative += n
        name = name_of(file, names)
        lines.append(f"| {i} | {file.removesuffix('.dat')} | {n} | {r.sets_with[file]} | "
                     f"{100 * cumulative / r.total:.1f} | {kind_of(name)} | {name} |")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.missing_parts",
                                     description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sets", nargs="+", help="set numbers such as 6378-1")
    group.add_argument("--sets-file", type=Path, help="an experiments.sets selection; its selected sets")
    group.add_argument("--all", action="store_true", help="every .mpd in the data directory")
    parser.add_argument("--data", type=Path, default=Path("data/omr"))
    parser.add_argument("--rebrickable", type=Path, default=Path("data/rebrickable/parts.csv.gz"))
    parser.add_argument("--top", type=int, default=120, help="rows in the ranked table")
    parser.add_argument("--out", type=Path, required=True, help="markdown file to write")
    args = parser.parse_args(argv)
    if args.all:
        paths = sorted(args.data.glob("*.mpd"))
        label = f"all {len(paths)} local OMR models"
    else:
        sets = json.loads(args.sets_file.read_text(encoding="utf-8"))["selected"] if args.sets_file else args.sets
        paths = [args.data / f"{s}.mpd" for s in sets]
        label = f"{len(paths)} sets"
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in paths]
    table = markdown(label, rank(texts), part_names(args.rebrickable), args.top)
    header = (f"# Parts the catalog cannot place, ranked ({len(BY_FILE)} known files)\n\n"
              f"`python -m brickwfc.experiments.missing_parts {' '.join(argv or [])}`\n\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header + table + "\n", encoding="utf-8")
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
