"""The training pool for proposal model v2 (M12e): every OMR model measured, the usable ones selected.

    python -m brickwfc.ldraw.omr_crawl --out data/omr            # once: every OMR model into data/omr
    python -m brickwfc.experiments.omr_pool --data data/omr      # rerun whenever parts.CATALOG changes

Reads the crawl's ``index.json`` and measures every model file on the catalog as it is now: part instances and
the recognized share (``experiments.coverage.set_coverage``), the parts that voxelize onto the stud grid
(``bricks.voxelize``, as ``coverage --on-grid``), and the on-grid build's extent against the token grid
(``bricks.tokens``: 64 x 64 studs, 192 plates). Measurements are cached per model in ``--cache`` under the
catalog's fingerprint, so a rerun after a catalog change measures everything again and an interrupted run
resumes.

Selection follows ``experiments.sets`` loosened to size: no theme filter (any OMR model, main or official
alternate), at least ``--min-share`` percent recognized, ``--min-on-grid`` percent of the recognized parts on
the grid and ``--min-grid-parts`` on-grid parts, not a flat panel (at most ``--flat-plates`` plates tall over at
least ``--flat-area`` square studs: the mosaics, whose parts are a picture of 1 x 1 plates, not a build), and no
re-releases: a model whose recognized inventory equals
one of an earlier set (by year, then index order) is dropped; models of the same set (alternates) never count
as re-releases of each other. Writes the pool (``--pool``, JSON: thresholds, catalog fingerprint, one row per
model, the selected files) and the report (``--results``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from brickwfc.bricks.colors import color_for_code
from brickwfc.bricks.parts import BY_FILE
from brickwfc.bricks.tokens import MAX_XZ, MAX_Y
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.coverage import set_coverage
from brickwfc.ldraw.mpd import PartInstance, flatten

MEASURE_VERSION = 2  # bump when the measurement itself changes (2: accessories held by frames, M12d batch 2)


def catalog_fingerprint() -> str:
    """A short hash of the LDraw file -> part mapping and every part's definition."""
    text = repr(sorted((file, repr(part)) for file, part in BY_FILE.items()))
    return hashlib.sha1(f"{MEASURE_VERSION}:{text}".encode("utf-8")).hexdigest()[:12]


@dataclass
class Measure:
    """One OMR model on the current catalog."""

    file: str
    parts: int  # part instances, primitives left out
    recognized: int  # instances in parts.CATALOG
    on_grid: int  # recognized instances on the stud grid, as ``coverage --on-grid``: kept parts + accessories they hold
    tilted: int
    off_grid: int
    overlapping: int
    extent: tuple[int, int, int]  # (Y plates, Z studs, X studs) of the on-grid build; zeros when empty
    inventory_key: str  # hash of the recognized (part, color) counts; "" when nothing is recognized
    top_missing: list[tuple[str, int]]
    error: str = ""
    contained: int = 0  # accessories (glass, panes, doors) held by kept frames; counted in on_grid, no cells or tokens

    @property
    def recognized_pct(self) -> float:
        return 100 * self.recognized / self.parts if self.parts else 0.0

    @property
    def on_grid_pct(self) -> float:
        """Percent of the recognized parts on the grid (``experiments.sets``'s criterion)."""
        return 100 * self.on_grid / self.recognized if self.recognized else 0.0

    def share(self, n: int) -> float:
        """``n`` as a percent of the model's parts."""
        return 100 * n / self.parts if self.parts else 0.0

    @property
    def shares(self) -> dict[str, float]:
        """Percent of the parts: unrecognized (no catalog part) and recognized but not placed on the grid, split
        into tilted (not a quarter turn about the vertical: sideways, upside down), off the stud grid (e.g. on a
        jumper's half-stud offset), overlapping, and accessories held by a frame that is itself off the grid; the
        rest is on the grid."""
        off = self.recognized - self.on_grid
        return {"unrecognized_pct": round(self.share(self.parts - self.recognized), 2),
                "off_grid_total_pct": round(self.share(off), 2),
                "tilted_pct": round(self.share(self.tilted), 2), "off_stud_grid_pct": round(self.share(self.off_grid), 2),
                "overlapping_pct": round(self.share(self.overlapping), 2),
                "accessory_off_pct": round(self.share(off - self.tilted - self.off_grid - self.overlapping), 2),
                "on_grid_parts_pct": round(self.share(self.on_grid), 2)}

    @property
    def fits_tokens(self) -> bool:
        y, z, x = self.extent
        return y <= MAX_Y and z <= MAX_XZ and x <= MAX_XZ


def inventory_key(instances: Sequence[PartInstance]) -> str:
    """The recognized (part, color) counts of a model as a hash (``experiments.sets``'s re-release test)."""
    counts: Counter[tuple[str, str]] = Counter()
    for inst in instances:
        part = BY_FILE.get(inst.part.lower())
        if part is not None:
            counts[(part.name, color_for_code(inst.color).name)] += 1
    return hashlib.sha1(repr(sorted(counts.items())).encode("utf-8")).hexdigest()[:16] if counts else ""


def measure(file: str, text: str) -> Measure:
    coverage = set_coverage(file, text)
    instances = flatten(text)
    placed, report = voxelize(instances)
    if placed:
        extent = (max(p.top + 1 for p in placed), max(p.z + p.shape.size_z for p in placed),
                  max(p.x + p.shape.size_x for p in placed))
    else:
        extent = (0, 0, 0)
    return Measure(file, coverage.parts, coverage.catalog, report.kept + report.contained, report.tilted,
                   report.off_grid, report.overlapping, extent, inventory_key(instances), coverage.top_missing,
                   contained=report.contained)


def _measure_path(path: Path) -> dict:
    try:
        return asdict(measure(path.name, path.read_text(encoding="utf-8", errors="replace")))
    except Exception as error:  # a malformed third-party file is reported, not fatal
        return asdict(Measure(path.name, 0, 0, 0, 0, 0, 0, (0, 0, 0), "", [], f"{type(error).__name__}: {error}"))


def _from_json(row: dict) -> Measure:
    return Measure(**{**row, "extent": tuple(row["extent"]), "top_missing": [tuple(t) for t in row["top_missing"]]})


def measure_all(files: Sequence[Path], cache: Path, workers: int, log=print) -> dict[str, Measure]:  # noqa: ANN001
    """Every file measured on the current catalog; cached in ``cache`` (JSON lines) under its fingerprint."""
    fingerprint = catalog_fingerprint()
    done: dict[str, Measure] = {}
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.pop("catalog") == fingerprint:
                done[row["file"]] = _from_json(row)
    todo = [p for p in files if p.name not in done]
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("a", encoding="utf-8") as f:
        def record(row: dict) -> None:
            f.write(json.dumps({"catalog": fingerprint, **row}) + "\n")
            f.flush()
            done[row["file"]] = _from_json(row)
            if len(done) % 100 == 0:
                log(f"measured {len(done)}/{len(files)}")

        if workers <= 1:
            for path in todo:
                record(_measure_path(path))
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for row in pool.map(_measure_path, todo, chunksize=4):
                    record(row)
    return {p.name: done[p.name] for p in files}


# Selection ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Thresholds:
    min_share: float = 50.0  # percent of parts recognized
    min_on_grid: float = 50.0  # percent of recognized parts on the grid
    min_grid_parts: int = 20  # on-grid parts
    flat_plates: int = 9  # a build at most this many plates tall ...
    flat_area: int = 1024  # ... over at least this many square studs (32 x 32) is a flat panel (a mosaic)


def model_rows(index: list[dict]) -> list[dict]:
    """One row per model of the crawl index: set, name, theme, year, model name, file, and whether it is the set's
    main model; an official alternate has ``alternate_of`` = its set number (it shares the set's inventory, so the
    export keeps it in the same split as its set)."""
    rows = []
    for s in index:
        first = s["models"][0]["file"] if s["models"] else None
        has_named = any(m["file"] == f"{s['number']}.mpd" for m in s["models"])
        for m in s["models"]:
            main = m.get("main")
            if main is None:  # an index written before the crawler marked main models
                main = m["file"] == (f"{s['number']}.mpd" if has_named else first)
            rows.append({"set": s["number"], "set_name": s["name"], "theme": s["theme"], "year": s["year"],
                         "model": m["name"], "file": m["file"], "main": main,
                         "alternate_of": "" if main else s["number"]})
    return rows


def reason(row: dict, m: Measure, t: Thresholds, seen: dict[str, str]) -> str:
    """"yes" for a selected model, otherwise why not. ``seen``: inventory key -> the set that first had it."""
    if m.error:
        return "unreadable"
    first = seen.get(m.inventory_key)
    if m.inventory_key and first is not None and first != row["set"]:
        return f"re-release of {first}"
    y, z, x = m.extent
    if 0 < y <= t.flat_plates and z * x >= t.flat_area:
        return "flat panel (mosaic)"
    if m.recognized_pct < t.min_share:
        return f"< {t.min_share:.0f}% recognized"
    if m.on_grid_pct < t.min_on_grid:
        return f"< {t.min_on_grid:.0f}% on grid"
    if m.on_grid < t.min_grid_parts:
        return f"< {t.min_grid_parts} on-grid parts"
    return "yes"


def select(rows: list[dict], measures: dict[str, Measure], t: Thresholds) -> list[dict]:
    """Every row with its measurement and selection reason; re-releases resolved oldest first."""
    order = sorted(range(len(rows)), key=lambda i: (rows[i]["year"] is None, rows[i]["year"] or 0, i))
    seen: dict[str, str] = {}
    out: list[dict | None] = [None] * len(rows)
    for i in order:
        row, m = rows[i], measures[rows[i]["file"]]
        why = reason(row, m, t, seen)
        if m.inventory_key:
            seen.setdefault(m.inventory_key, row["set"])
        out[i] = {**row, **asdict(m), "recognized_pct": round(m.recognized_pct, 2), "on_grid_pct": round(m.on_grid_pct, 2), **m.shares,
                  "fits_tokens": m.fits_tokens, "selected": why}
    return [r for r in out if r is not None]


# Report ---------------------------------------------------------------------------------------------------


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}" if d else "0"


def _quantiles(values: Iterable[float]) -> str:
    v = np.array(list(values), dtype=float)
    if not len(v):
        return "—"
    return " / ".join(f"{np.percentile(v, q):.0f}" for q in (10, 50, 90)) + f" (max {v.max():.0f})"


def loss_table(readable: list[dict], chosen: list[dict]) -> list[str]:
    """Where the parts that are not on the grid go: unrecognized vs recognized but off the grid (by cause), as a share of
    all part instances. After a catalog change the off-grid share says whether sideways building is the next step."""
    lines = ["**Parts not on the grid, as a share of all part instances** (per model in the pool file: "
             "`unrecognized_pct`, `off_grid_total_pct` = `tilted_pct` + `off_stud_grid_pct` + `overlapping_pct` + "
             "`accessory_off_pct`). Tilted = not a quarter turn about the vertical (sideways, upside down, angled); off "
             "the stud grid = a recognized part at a fractional stud or plate offset (jumper offsets); accessory = glass, "
             "a pane or a door held by a frame that is itself off the grid. On grid counts the accessories kept frames "
             "hold, as `coverage --on-grid` does.", "",
             "| models | unrecognized | off grid, all causes | tilted | off the stud grid | overlapping | accessory | "
             "on grid | median model: unrecognized / off grid |", "|---|---|---|---|---|---|---|---|---|"]
    for label, rows in (("every readable model", readable), ("pool", chosen)):
        parts = sum(r["parts"] for r in rows)
        sums = {k: sum(r[k] for r in rows) for k in ("recognized", "on_grid", "tilted", "off_grid", "overlapping")}
        off_all = sums["recognized"] - sums["on_grid"]
        accessory = off_all - sums["tilted"] - sums["off_grid"] - sums["overlapping"]
        un = np.median([r["unrecognized_pct"] for r in rows]) if rows else 0.0
        off = np.median([r["off_grid_total_pct"] for r in rows]) if rows else 0.0
        lines.append(f"| {label} ({len(rows)}) | {_pct(parts - sums['recognized'], parts)}% | "
                     f"{_pct(off_all, parts)}% | {_pct(sums['tilted'], parts)}% | "
                     f"{_pct(sums['off_grid'], parts)}% | {_pct(sums['overlapping'], parts)}% | {_pct(accessory, parts)}% | "
                     f"{_pct(sums['on_grid'], parts)}% | {un:.1f}% / {off:.1f}% |")
    return lines


def decisions(chosen: list[dict], t: Thresholds) -> list[str]:
    """The selection decisions (session B, M12e) with the numbers that support them, regenerated on every rerun."""
    parts = sum(r["parts"] for r in chosen)
    tilted = sum(r["tilted"] for r in chosen)
    off = sum(r["off_grid"] for r in chosen)
    return [
        "## Decisions (session B, 2026-10-15)", "",
        "- **No theme filter.** `experiments/sets.py` kept building themes (the 28 M10 sets). The model learns which "
        "parts go where, and vehicles, castles and trains place the same plates, bricks, slopes and tiles. The coverage "
        "thresholds already drop builds made mostly of parts the catalog lacks (Technic, minifigures, wheels): "
        "the pool's themes are listed below.",
        f"- **The M10 thresholds are kept** (>= {t.min_share:.0f}% recognized, >= {t.min_on_grid:.0f}% of the recognized "
        f"parts on the grid). The size floor is lowered from 50 parts to {t.min_grid_parts} on-grid parts: that is the "
        "loosening to size. A small model is a short sequence, not a wrong one.",
        "- **Flat panels are dropped.** These are the mosaics: 2,400–10,500 1 x 1 plates and tiles 8 plates tall. They "
        "would have been 22% of the pool's on-grid parts while teaching a picture, not a build. The rule is "
        f"geometric (<= {t.flat_plates} plates over >= {t.flat_area} square studs). On this catalog it catches exactly "
        "those 9 models; a low car or train is narrow, so it is not caught.",
        "- **Official alternates are kept** as their own sequences (`main` false, `alternate_of` = their set). More "
        "builds per inventory is what the model should learn. The export splits by set number, so a held-out set "
        "holds out its alternates too.",
        "- **Re-releases** (the same recognized inventory under a later set number) are dropped; the oldest set keeps "
        "it, as in `experiments/sets.py`.",
        f"- **Off the grid, by cause, in the pool:** tilted {_pct(tilted, parts)}% vs off the stud grid "
        f"{_pct(off, parts)}% of all part instances. Tilted parts (sideways, upside down, angled) are "
        + (f"{tilted / off:.1f}x" if off else "far more than") + " the jumper-offset kind. If sideways building were "
        "supported, those parts would be the gain.",
    ]


def display_theme(theme: str) -> str:
    """An OMR theme name for the write-up, without the trademark prefix some theme names carry (CLAUDE.md: no
    trademark in output); the pool file keeps the OMR's names as data."""
    return theme.removeprefix("LEGO ").strip() or "(none)"


def report(table: list[dict], counts: dict, t: Thresholds, fingerprint: str, catalog_parts: int,
           demo: Sequence[str]) -> str:
    chosen = [r for r in table if r["selected"] == "yes"]
    readable = [r for r in table if not r["error"]]
    lines = ["# M12e: the OMR training pool", "",
             "`python -m brickwfc.ldraw.omr_crawl --out data/omr` then `python -m brickwfc.experiments.omr_pool "
             "--data data/omr` (reruns in one command when `parts.CATALOG` changes; the measurement is cached per "
             f"catalog fingerprint). Catalog: **{catalog_parts} parts**, fingerprint `{fingerprint}`.", "",
             "## The repository", "",
             f"- OMR sets in the index: **{counts['sets']}**; models listed: **{counts['models']}** "
             f"({counts['main']} main models, {counts['models'] - counts['main']} official alternates).",
             f"- Models on disk: **{counts['on_disk']}**; failed downloads: {counts['failed']}; unreadable: "
             f"{len(table) - len(readable)}.", "",
             "## Every model on the current catalog", "",
             "| models | part instances | recognized | recognized % | on grid | on grid % of parts | on grid % of recognized |",
             "|---|---|---|---|---|---|---|"]
    parts = sum(r["parts"] for r in readable)
    rec = sum(r["recognized"] for r in readable)
    grid = sum(r["on_grid"] for r in readable)
    lines.append(f"| {len(readable)} | {parts} | {rec} | {_pct(rec, parts)} | {grid} | {_pct(grid, parts)} | {_pct(grid, rec)} |")
    lines += ["", *loss_table(readable, chosen)]
    lines += ["", "Per model, 10th / 50th / 90th percentile: "
              f"parts {_quantiles(r['parts'] for r in readable)}; recognized % "
              f"{_quantiles(r['recognized_pct'] for r in readable)}; on-grid % of recognized "
              f"{_quantiles(r['on_grid_pct'] for r in readable)}.", "",
              "## Selection", "",
              f"`experiments/sets.py`'s criteria loosened to size: no theme filter, **>= {t.min_share:.0f}% recognized**, "
              f"**>= {t.min_on_grid:.0f}% of the recognized parts on the grid**, **>= {t.min_grid_parts} on-grid parts**, "
              f"**not a flat panel** (<= {t.flat_plates} plates tall over >= {t.flat_area} square studs: the mosaics), "
              "no re-releases (identical recognized inventory; the oldest set keeps it; alternates of one set never "
              "collide).", "", "| reason | models |", "|---|---|"]
    reasons = Counter(r["selected"] if not r["selected"].startswith("re-release") else "re-release" for r in table)
    lines += [f"| {k} | {v} |" for k, v in reasons.most_common()]
    c_parts = sum(r["parts"] for r in chosen)
    c_rec = sum(r["recognized"] for r in chosen)
    c_grid = sum(r["on_grid"] for r in chosen)
    lines += ["", f"**Pool: {len(chosen)} models from {len({r['set'] for r in chosen})} sets** "
              f"({sum(r['main'] for r in chosen)} main, {sum(not r['main'] for r in chosen)} alternates); "
              f"**{c_parts} part instances, {c_rec} recognized ({_pct(c_rec, c_parts)}%), {c_grid} on the grid** "
              f"({_pct(c_grid, c_parts)}% of the instances). On-grid parts per model "
              f"{_quantiles(r['on_grid'] for r in chosen)}.",
              f"- Larger than the token grid (64 x 64 studs x 192 plates): {sum(not r['fits_tokens'] for r in chosen)} "
              "models (the export crops them; `experiments/export_tokens.py`).",
              "- Demo sets (held out of training by the export): "
              + ", ".join(f"{d} {'in the pool' if any(r['set'] == d and r['selected'] == 'yes' for r in chosen) else 'not in the pool'}"
                          for d in demo) + ".", "",
              *decisions(chosen, t), "",
              "## Pool by theme", "", "| theme | models | on-grid parts |", "|---|---|---|"]
    by_theme: dict[str, list[dict]] = {}
    for r in chosen:
        by_theme.setdefault(display_theme(r["theme"]), []).append(r)
    for theme, rs in sorted(by_theme.items(), key=lambda kv: -sum(r["on_grid"] for r in kv[1])):
        lines.append(f"| {theme} | {len(rs)} | {sum(r['on_grid'] for r in rs)} |")
    lines += ["", "## Most common parts the catalog misses (all readable models)", "",
              "| part | instances |", "|---|---|"]
    missing: Counter[str] = Counter()
    for r in readable:
        missing.update(dict((name, n) for name, n in r["top_missing"]))
    lines += [f"| {name} | {n} |" for name, n in missing.most_common(25)]
    lines += ["", "(Per model only its five most common missing parts are kept, so this undercounts the tail.)"]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.omr_pool", description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data/omr"), help="the crawl's directory (index.json, *.mpd)")
    parser.add_argument("--min-share", type=float, default=Thresholds.min_share)
    parser.add_argument("--min-on-grid", type=float, default=Thresholds.min_on_grid)
    parser.add_argument("--min-grid-parts", type=int, default=Thresholds.min_grid_parts)
    parser.add_argument("--flat-plates", type=int, default=Thresholds.flat_plates, help="flat panel: at most this tall")
    parser.add_argument("--flat-area", type=int, default=Thresholds.flat_area, help="flat panel: at least this many studs")
    parser.add_argument("--demo", nargs="*", default=["6378-1", "31048-1"], help="demo sets, reported here")
    parser.add_argument("--cache", type=Path, default=Path("out/omr_pool/measure.jsonl"))
    parser.add_argument("--pool", type=Path, default=Path("results/m12e_omr_pool.json"))
    parser.add_argument("--results", type=Path, default=Path("results/m12e_omr_pool.md"))
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 3) - 2))
    args = parser.parse_args(argv)

    from brickwfc.bricks.parts import CATALOG

    index = json.loads((args.data / "index.json").read_text(encoding="utf-8"))
    rows = model_rows(index)
    present = [r for r in rows if (args.data / r["file"]).exists()]
    measures = measure_all([args.data / r["file"] for r in present], args.cache, args.workers)
    t = Thresholds(args.min_share, args.min_on_grid, args.min_grid_parts, args.flat_plates, args.flat_area)
    table = select(present, measures, t)
    counts = {"sets": len(index), "models": len(rows), "main": sum(r["main"] for r in rows), "on_disk": len(present),
              "failed": len(rows) - len(present)}
    fingerprint = catalog_fingerprint()
    args.pool.parent.mkdir(parents=True, exist_ok=True)
    args.pool.write_text(json.dumps({"catalog": fingerprint, "catalog_parts": len(CATALOG), "thresholds": asdict(t),
                                     "counts": counts, "selected": [r["file"] for r in table if r["selected"] == "yes"],
                                     "models": table}, separators=(",", ":")), encoding="utf-8")
    text = report(table, counts, t, fingerprint, len(CATALOG), args.demo)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
