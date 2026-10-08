"""M13: diversity of each generator's candidates, from the alternate-build runs already on disk (no builds).

    python -m brickwfc.experiments.diversity_pass [--base .] [--roots out/alt/* ...]

A run folder is one ``alt`` run: ``candidates.jsonl`` (its first line is the setup key: source, inventory,
grid, generator, ...; then one candidate per line) and, when the run finished, ``stats.json`` (its config and
the selected builds). For each run this computes ``funnel.diversity`` on

- the **verified** candidates: valid (every check passed) and at least the funnel's size floor (the
  ``min_size_quantile`` of the valid candidates' contact events), i.e. what reaches dedupe; and
- the **selected** top-k (``stats.json``'s ``selected`` seeds), when the run finished,

with ``alt.features.feature_vector`` as features and the run's dedupe threshold (``stats.json``'s config, or
the ``AltConfig`` default) as the threshold. Runs differ in how many candidates they made (50 to 200), and
the effective number grows with that, so tables compare ``effective_share`` = effective / verified.

The feature distances' scale depends on the setup (grid height adds per-layer entries; the M12 demo's
median pair distance is ~0.2, M12's cubes ~0.8), so no one threshold is comparable across setups: at the
dedupe threshold (0.05) nearly every verified candidate is distinct. Each row therefore also has the
**profile** ``effective_share_at`` over ``PROFILE`` thresholds; compare generators only on runs of the same
setup (the same inventory, grid and target), across the profile.
A run still being written is read up to its last complete line.

Each run is labelled by its generator as the paper tables name them: ``pipeline`` (D2 with balance and the
one-piece repair, the M12 defaults), ``pipeline_wfc`` (WFC as the generator), or ``d2`` with the switched-off
parts (``d2_noconnect``, ``d2_nobalance``, ...). Results are cached per run by the candidate file's size and
modification time (``--cache``), so a rerun only reads runs that changed. Writes ``results/m13_diversity.json``
(one row per run) and ``results/m13_diversity.md``.
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.alt.candidates import Candidate
from brickwfc.alt.features import feature_vector
from brickwfc.alt.pipeline import AltConfig
from brickwfc.bricks.style import events
from brickwfc.funnel.diversity import diversity

DEFAULT_ROOTS = ("out/alt/*", "out/m12_2b/*/*", "out/m12_demo/*/*", "out/m12b_brickgpt/*/*")
PROFILE = (0.05, 0.1, 0.2, 0.3, 0.5)  # thresholds of the diversity profile
CACHE_VERSION = 3


def label(key: dict) -> str:
    """The generator name used by the paper tables."""
    if key.get("generator") == "wfc":
        return "pipeline_wfc"
    off = [name for name in ("balanced", "connect") if not key.get(name, True)]
    return "pipeline" if not off else "d2_" + "_".join("no" + name.removesuffix("d") for name in off)


def read_run(path: Path) -> tuple[dict, list[Candidate]]:
    """(setup key, candidates) of a ``candidates.jsonl``, ignoring an incomplete last line."""
    lines = path.read_text(encoding="utf-8").splitlines()
    key = json.loads(lines[0])["key"]
    candidates = []
    for line in lines[1:]:
        if not line.strip():
            continue
        try:
            candidates.append(Candidate.from_json(json.loads(line)))
        except (json.JSONDecodeError, KeyError):  # a line being written
            continue
    return key, candidates


def verified(candidates: Sequence[Candidate], min_size_quantile: float) -> list[Candidate]:
    """Valid candidates with at least the size floor of contact events, as in ``alt.pipeline.run_funnel``."""
    valid = [c for c in candidates if c.valid]
    if not valid:
        return []
    counts = {c.seed: events(c.placed).count for c in valid}
    floor = int(np.quantile(list(counts.values()), min_size_quantile, method="lower"))
    return [c for c in valid if counts[c.seed] >= floor]


def analyze(folder: Path, profile: Sequence[float] = PROFILE) -> dict:
    """One row: the run's setup, and the diversity of its verified and selected candidates."""
    key, candidates = read_run(folder / "candidates.jsonl")
    stats_path = folder / "stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else None
    config = {**asdict(AltConfig()), **(stats["config"] if stats else {})}
    grid = tuple(key["grid"])
    colors = sorted({color for _, color, _ in key["inventory"]})  # distances do not depend on the color order
    threshold = config["dedupe_threshold"]

    def features(chosen: Sequence[Candidate]) -> np.ndarray:
        rows = [feature_vector(c.placed, grid, colors) for c in chosen]
        return np.array(rows) if rows else np.zeros((0, 1))

    checked = verified(candidates, config["min_size_quantile"])
    d = diversity(features(checked), threshold)
    row = {"run": folder.as_posix(), "generator": label(key), "alt_generator": key.get("generator"),
           "source": key.get("source"), "shape": key.get("mask") is not None, "grid_YZX": list(grid),
           "threshold": threshold, "candidates": len(candidates), "valid": sum(c.valid for c in candidates),
           "verified": d.designs, "effective": d.effective,
           "effective_share": d.effective_share if d.designs else None,  # no designs: no share (not 0)
           "mean_distance": d.mean_distance, "finished": stats is not None,
           "effective_share_at": {f"{t:g}": diversity(f, t).effective_share if d.designs else None
                                  for f in [features(checked)] for t in profile}}
    if stats is not None:
        by_seed = {c.seed: c for c in candidates}
        selected = [by_seed[r["seed"]] for r in stats.get("selected", []) if r["seed"] in by_seed]
        s = diversity(features(selected), threshold)
        row.update(selected=s.designs, selected_effective=s.effective,
                   selected_effective_share=s.effective_share if s.designs else None,
                   selected_mean_distance=s.mean_distance)
    return row


def run_folders(base: Path, roots: Sequence[str]) -> list[Path]:
    found = {Path(p).parent for root in roots for p in glob.glob(str(base / root / "candidates.jsonl"))}
    return sorted(found, key=lambda p: p.as_posix())


def stamp(folder: Path) -> list:
    """What a cached row depends on: the candidate file's and stats.json's size and modification time."""
    out: list = [CACHE_VERSION]
    for name in ("candidates.jsonl", "stats.json"):
        path = folder / name
        out += [path.stat().st_size, path.stat().st_mtime_ns] if path.exists() else [None, None]
    return out


def collect(folders: Sequence[Path], cache_path: Path, base: Path) -> list[dict]:
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    rows = []
    for folder in folders:
        name = folder.relative_to(base).as_posix() if folder.is_relative_to(base) else folder.as_posix()
        entry = cache.get(name)
        if entry is None or entry["stamp"] != stamp(folder):
            row = analyze(folder)
            row["run"] = name
            entry = cache[name] = {"stamp": stamp(folder), "row": row}
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache), encoding="utf-8")  # saved per run: a killed pass resumes
        rows.append(entry["row"])
    return rows


def markdown(rows: Sequence[dict]) -> str:
    lines = ["# M13: diversity of the generators' candidates", "",
             "`python -m brickwfc.experiments.diversity_pass` (`funnel/diversity.py`). Per alt run: the effective number of "
             "distinct designs (Leinster-Cobbold order 1, threshold = the run's dedupe threshold) among the verified "
             "candidates and among the selected top-k; share = effective / designs.", "",
             "## Per generator (mean over runs)", "",
             "| generator | runs | verified per run | effective share % | mean distance | selected: effective share % |",
             "|---|---|---|---|---|---|"]
    for generator in sorted({r["generator"] for r in rows}):
        mine = [r for r in rows if r["generator"] == generator and r["verified"]]
        if not mine:
            lines.append(f"| {generator} | 0 | — | — | — | — |")
            continue
        selected = [r["selected_effective_share"] for r in mine if r.get("selected_effective_share") is not None]
        shown = f"{100 * statistics.fmean(selected):.1f}" if selected else "—"
        lines.append(f"| {generator} | {len(mine)} | {statistics.fmean(r['verified'] for r in mine):.0f} | "
                     f"{100 * statistics.fmean(r['effective_share'] for r in mine):.1f} | "
                     f"{statistics.fmean(r['mean_distance'] for r in mine):.3f} | {shown} |")
    lines += ["", "The share at the dedupe threshold is close to 100% almost everywhere: at that distance nearly every "
              "verified candidate is distinct. The profile below (share % at larger thresholds) is what separates runs; "
              "compare generators only on runs of the same setup.", "",
              "## Per run", "",
              "| run | generator | candidates | valid | verified | effective | share % | mean distance | "
              + " | ".join(f"share % @{t:g}" for t in PROFILE) + " | selected | selected effective |",
              "|---|---|---|---|---|---|---|---|" + "---|" * len(PROFILE) + "---|---|"]
    for r in rows:
        pct = lambda v: "—" if v is None else f"{100 * v:.0f}"  # noqa: E731
        sel = f"{r['selected']} | {r['selected_effective']:.1f}" if r.get("selected") is not None else "— | —"
        prof = " | ".join(pct(r["effective_share_at"][f"{t:g}"]) for t in PROFILE)
        lines.append(f"| {r['run']} | {r['generator']} | {r['candidates']} | {r['valid']} | {r['verified']} | "
                     f"{r['effective']:.1f} | {pct(r['effective_share'])} | {r['mean_distance']:.3f} | {prof} | {sel} |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.diversity_pass", description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, default=Path("."), help="directory the run globs are relative to")
    parser.add_argument("--roots", nargs="+", default=list(DEFAULT_ROOTS), help="globs of run folders under --base")
    parser.add_argument("--cache", type=Path, default=Path("out/m13_diversity/cache.json"))
    parser.add_argument("--out", type=Path, default=Path("results/m13_diversity.json"))
    args = parser.parse_args(argv)
    folders = run_folders(args.base, args.roots)
    rows = collect(folders, args.cache, args.base)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    text = markdown(rows)
    args.out.with_suffix(".md").write_text(text, encoding="utf-8")
    print(text)
    print(f"{len(rows)} runs; wrote {args.out} and {args.out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
