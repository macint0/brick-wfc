"""M12c: do Rebrickable inventories agree with the inventories read from the LDraw models? (the 28 M10 sets)

    python -m brickwfc.experiments.rebrickable_check --omr data/omr --out results/m12c_rebrickable.md

For each set, two inventories over ``parts.CATALOG``: from the OMR model (``inventory.inventory_from_mpd``,
every catalog part in the model) and from Rebrickable (``bricks.rebrickable``, the latest inventory without
spares). Agreement is the weighted Jaccard index sum min(a, b) / sum max(a, b) over the counts, computed three
ways: per (part, color), per part (colors pooled), per color (parts pooled), so a part-numbering difference
and a color-mapping difference show up separately. Systematic differences are the parts and colors whose
count differs in the same direction across sets; the report also lists the colors guessed by nearest RGB and
the parts found only through a print or mold parent. Writes the report and ``<out>.json``.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

from brickwfc.bricks.inventory import inventory_from_mpd
from brickwfc.bricks.rebrickable import DATA_DIR, Rebrickable
from brickwfc.ldraw.fetch import fetch_set

Inventory = Mapping[tuple[str, str], int]


def jaccard(a: Mapping, b: Mapping) -> float:
    keys = set(a) | set(b)
    top = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    return sum(min(a.get(k, 0), b.get(k, 0)) for k in keys) / top if top else 1.0


def pooled(inventory: Inventory, index: int) -> Counter:
    out: Counter = Counter()
    for key, count in inventory.items():
        out[key[index]] += count
    return out


def compare(omr: Inventory, rb: Inventory) -> dict:
    return {"omr_parts": sum(omr.values()), "rb_parts": sum(rb.values()), "agreement": jaccard(omr, rb),
            "agreement_parts": jaccard(pooled(omr, 0), pooled(rb, 0)), "agreement_colors": jaccard(pooled(omr, 1), pooled(rb, 1))}


def differences(pairs: Sequence[tuple[Inventory, Inventory]], index: int) -> list[tuple[str, int, int, int]]:
    """(name, total Rebrickable - OMR count, sets where Rebrickable has more, sets where it has fewer) per part
    (``index`` 0) or color (1), largest total difference first."""
    total: Counter = Counter()
    more: Counter = Counter()
    fewer: Counter = Counter()
    for omr, rb in pairs:
        a, b = pooled(omr, index), pooled(rb, index)
        for k in set(a) | set(b):
            d = b.get(k, 0) - a.get(k, 0)
            total[k] += d
            more[k] += d > 0
            fewer[k] += d < 0
    return sorted(((k, total[k], more[k], fewer[k]) for k in total if total[k] or more[k] or fewer[k]),
                  key=lambda r: (-abs(r[1]), r[0]))


def largest_differences(omr: Inventory, rb: Inventory, top: int = 5) -> list[tuple[str, str, int]]:
    """(part, color, Rebrickable - OMR) for the (part, color) pairs that differ most."""
    diffs = [(k, rb.get(k, 0) - omr.get(k, 0)) for k in set(omr) | set(rb)]
    return [(k[0], k[1], d) for k, d in sorted(diffs, key=lambda t: (-abs(t[1]), t[0])) if d][:top]


def report(rows: Sequence[dict], part_diffs: Sequence[tuple], color_diffs: Sequence[tuple], guessed: Counter,
           via_parent: Counter, ignored: Counter, top: int = 15, outlier_below: float = 0.9) -> str:
    mean = lambda key: statistics.fmean(r[key] for r in rows)  # noqa: E731
    median = lambda key: statistics.median(r[key] for r in rows)  # noqa: E731
    lines = ["# M12c: Rebrickable inventories vs the OMR models (28 M10 sets)", "",
             "`python -m brickwfc.experiments.rebrickable_check`. Inventories over the part catalog; agreement = weighted "
             "Jaccard sum min / sum max of the counts (1 = identical).", "",
             f"**Agreement over {len(rows)} sets:** per (part, color) mean {mean('agreement'):.3f} (median "
             f"{median('agreement'):.3f}); per part {mean('agreement_parts'):.3f}; per color {mean('agreement_colors'):.3f}. "
             f"Catalog parts: OMR {sum(r['omr_parts'] for r in rows)}, Rebrickable {sum(r['rb_parts'] for r in rows)}.", "",
             "| set | name | year | inventory version | OMR parts | Rebrickable parts | agreement | parts only | colors only |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['set']} | {r['name']} | {r['year']} | {r['inventory_version']} | {r['omr_parts']} | {r['rb_parts']} | "
                     f"{r['agreement']:.3f} | {r['agreement_parts']:.3f} | {r['agreement_colors']:.3f} |")

    def diff_table(title: str, diffs: Sequence[tuple]) -> list[str]:
        out = ["", f"## {title}", "", "| name | Rebrickable - OMR (all sets) | sets with more | sets with fewer |", "|---|---|---|---|"]
        return out + [f"| {k} | {d:+d} | {m} | {f} |" for k, d, m, f in diffs[:top]]

    outliers = [r for r in rows if r["agreement"] < outlier_below]
    lines += ["", f"## Sets below {outlier_below:g} agreement", ""]
    lines += [f"- {r['set']} ({r['agreement']:.3f}): " + ", ".join(f"{p} {c} {d:+d}" for p, c, d in r["largest_differences"])
              for r in outliers] or ["none"]
    lines += diff_table("Systematic part differences (colors pooled)", part_diffs)
    lines += diff_table("Systematic color differences (parts pooled)", color_diffs)
    lines += ["", "## Mapping notes", "",
              "Colors guessed by nearest RGB (Rebrickable name -> our color: parts): "
              + (", ".join(f"{k}: {v}" for k, v in guessed.most_common()) or "none") + ".", "",
              "Parts found through a print/mold parent (top): " + (", ".join(f"{k}: {v}" for k, v in via_parent.most_common(top)) or "none") + ".", "",
              "Rebrickable parts not in the catalog (top, all sets): " + ", ".join(f"{k}: {v}" for k, v in ignored.most_common(10)) + "."]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.rebrickable_check", description=__doc__.splitlines()[0])
    parser.add_argument("--sets-file", type=Path, default=Path("results/sets_selection.json"))
    parser.add_argument("--omr", type=Path, default=Path("data/omr"))
    parser.add_argument("--rebrickable", type=Path, default=DATA_DIR)
    parser.add_argument("--out", type=Path, default=Path("results/m12c_rebrickable.md"))
    args = parser.parse_args(argv)
    sets = json.loads(args.sets_file.read_text(encoding="utf-8"))["selected"]
    db = Rebrickable(args.rebrickable)
    found = db.inventories(sets)
    rows, pairs = [], []
    guessed: Counter = Counter()
    via_parent: Counter = Counter()
    ignored: Counter = Counter()
    for s in sets:
        omr, _, _ = inventory_from_mpd(fetch_set(s, args.omr).read_text(encoding="utf-8", errors="replace"))
        rb, _, _, info = found[s]
        rows.append({"set": s, "name": info.name, "year": info.year, "inventory_version": info.inventory_version,
                     **compare(omr, rb), "largest_differences": largest_differences(omr, rb), "rebrickable": info.to_json()})
        pairs.append((omr, rb))
        guessed.update(info.guessed_colors)
        via_parent.update(info.via_parent)
        ignored.update(info.ignored)
    part_diffs, color_diffs = differences(pairs, 0), differences(pairs, 1)
    text = report(rows, part_diffs, color_diffs, guessed, via_parent, ignored)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    args.out.with_suffix(".json").write_text(json.dumps({"sets": rows, "part_differences": part_diffs,
                                                         "color_differences": color_diffs}, indent=2), encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
