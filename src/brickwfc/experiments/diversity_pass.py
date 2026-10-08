"""M13: diversity of each generator's candidates, from the alternate-build runs already on disk (no builds).

    python -m brickwfc.experiments.diversity_pass [--base .] [--roots out/alt/* ...]

**Rule:** within a setup (same inventory, grid and target), feature distances are measured in units of the
median pairwise distance among the D2-pipeline candidates of that setup, and two designs count as distinct
when they are at least ``NORM_THRESHOLD`` = 0.5 of those units apart (half a typical D2 distance).

A run folder is one ``alt`` run: ``candidates.jsonl`` (its first line is the setup key: source, inventory,
grid, target mask, generator, ...; then one candidate per line) and, when the run finished, ``stats.json``
(its config and the selected builds). For each run this takes

- the **verified** candidates: valid (every check passed) and at least the funnel's size floor (the
  ``min_size_quantile`` of the valid candidates' contact events), i.e. what reaches dedupe; and
- the **selected** top-k (``stats.json``'s ``selected`` seeds), when the run finished,

with ``alt.features.feature_vector`` as features, and reports for both (``funnel.diversity``):

- ``effective_share_norm``: effective number of distinct designs / designs, at the rule's threshold (the
  main number; runs make 50 to 200 candidates, and the effective number grows with that);
- ``mean_distance_norm``: mean pairwise distance in the setup's units (1 = as spread out as D2 typically is);
- the raw numbers (``effective_share`` at the run's dedupe threshold, ``mean_distance``) and the **profile**
  ``effective_share_at`` over the raw thresholds ``PROFILE`` (the appendix).

Why normalized: the raw distance scale depends on the setup (grid height adds per-layer entries; the M12
demo's median pair distance is ~0.2, M12's cubes ~0.8, some tall BrickGPT targets ~3), so no raw threshold is
comparable across setups, and at the dedupe threshold (0.05) nearly every verified candidate is distinct.
The setup's unit pools the within-run pair distances of all its D2-pipeline runs; a setup without a
D2-pipeline run with at least two verified candidates has no unit, and its normalized numbers are null ("—").

Runs are labelled by generator as the paper tables name them: ``pipeline`` (D2 with balance and the one-piece
repair, the M12 defaults: the reference), ``pipeline_wfc`` (WFC as the generator), or ``d2`` with the switched-
off parts (``d2_noconnect``, ...). A run with no verified candidates has no shares (null, not 0). A run still
being written is read up to its last complete line. Per-run results and features are cached by the files'
size and modification time (``--cache``, features next to it), so a rerun only reads runs that changed.
Writes ``results/m13_diversity.json`` (one row per run) and ``results/m13_diversity.md``.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
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
from brickwfc.funnel.diversity import diversity, mean_pairwise_distance, pairwise_distances

DEFAULT_ROOTS = ("out/alt/*", "out/m12_2b/*/*", "out/m12_demo/*/*", "out/m12b_brickgpt/*/*")
PROFILE = (0.05, 0.1, 0.2, 0.3, 0.5)  # raw thresholds of the appendix profile
NORM_THRESHOLD = 0.5  # in units of the setup's median D2-pipeline pair distance
REFERENCE = "pipeline"
SETUP_FIELDS = ("source", "inventory", "grid", "mask", "preferred")
CACHE_VERSION = 4


def label(key: dict) -> str:
    """The generator name used by the paper tables."""
    if key.get("generator") == "wfc":
        return "pipeline_wfc"
    off = [name for name in ("balanced", "connect") if not key.get(name, True)]
    return REFERENCE if not off else "d2_" + "_".join("no" + name.removesuffix("d") for name in off)


def setup_id(key: dict) -> str:
    """Short id of what the candidates are built from and into (not how): inventory, grid, target."""
    text = json.dumps({f: key.get(f) for f in SETUP_FIELDS}, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:12]


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


def share(features: np.ndarray, threshold: float) -> float | None:
    """Effective share of distinct designs, None for no designs."""
    return diversity(features, threshold).effective_share if len(features) else None


def analyze(folder: Path) -> tuple[dict, np.ndarray, np.ndarray]:
    """(row of raw numbers, verified candidates' features, indices of the selected ones among them)."""
    key, candidates = read_run(folder / "candidates.jsonl")
    stats_path = folder / "stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else None
    config = {**asdict(AltConfig()), **(stats["config"] if stats else {})}
    grid = tuple(key["grid"])
    colors = sorted({color for _, color, _ in key["inventory"]})  # distances do not depend on the color order
    threshold = config["dedupe_threshold"]
    checked = verified(candidates, config["min_size_quantile"])
    rows = [feature_vector(c.placed, grid, colors) for c in checked]
    features = np.array(rows) if rows else np.zeros((0, 1))
    d = diversity(features, threshold)
    row = {"run": folder.as_posix(), "generator": label(key), "alt_generator": key.get("generator"),
           "source": key.get("source"), "setup": setup_id(key), "shape": key.get("mask") is not None,
           "grid_YZX": list(grid), "threshold": threshold, "candidates": len(candidates),
           "valid": sum(c.valid for c in candidates), "verified": d.designs, "effective": d.effective,
           "effective_share": share(features, threshold), "mean_distance": d.mean_distance,
           "effective_share_at": {f"{t:g}": share(features, t) for t in PROFILE}, "finished": stats is not None}
    selected = np.zeros(0, dtype=np.int64)
    if stats is not None:
        index = {c.seed: i for i, c in enumerate(checked)}
        selected = np.array([index[r["seed"]] for r in stats.get("selected", []) if r["seed"] in index], dtype=np.int64)
        row["selected"] = len(selected)
    return row, features, selected


# Per-setup normalization ------------------------------------------------------------------------------


def setup_units(runs: Sequence[tuple[dict, np.ndarray, np.ndarray]]) -> dict[str, float]:
    """Per setup: the median of the within-run pair distances pooled over its reference (D2-pipeline) runs."""
    pooled: dict[str, list[np.ndarray]] = {}
    for row, features, _ in runs:
        if row["generator"] == REFERENCE and len(features) >= 2:
            pooled.setdefault(row["setup"], []).append(pairwise_distances(features)[np.triu_indices(len(features), 1)])
    units = {setup: float(np.median(np.concatenate(parts))) for setup, parts in pooled.items()}
    return {setup: unit for setup, unit in units.items() if unit > 0}


def normalized(row: dict, features: np.ndarray, selected: np.ndarray, unit: float | None) -> dict:
    """The row with the rule's numbers for the verified and the selected candidates (None without a unit)."""
    out = {**row, "unit": unit}
    for prefix, chosen in (("", features), ("selected_", features[selected] if len(selected) else features[:0])):
        if prefix and "selected" not in row:
            continue
        ok = unit is not None and len(chosen) > 0
        out[f"{prefix}effective_share_norm"] = share(chosen / unit, NORM_THRESHOLD) if ok else None
        out[f"{prefix}mean_distance_norm"] = mean_pairwise_distance(chosen) / unit if ok and len(chosen) > 1 else None
    return out


# Running ----------------------------------------------------------------------------------------------


def run_folders(base: Path, roots: Sequence[str]) -> list[Path]:
    found = {Path(p).parent for root in roots for p in glob.glob(str(base / root / "candidates.jsonl"))}
    return sorted(found, key=lambda p: p.as_posix())


def stamp(folder: Path) -> list:
    """What a cached run depends on: the candidate file's and stats.json's size and modification time."""
    out: list = [CACHE_VERSION]
    for name in ("candidates.jsonl", "stats.json"):
        path = folder / name
        out += [path.stat().st_size, path.stat().st_mtime_ns] if path.exists() else [None, None]
    return out


def collect(folders: Sequence[Path], cache_path: Path, base: Path) -> list[tuple[dict, np.ndarray, np.ndarray]]:
    """(row, features, selected) per run, from the cache where the run has not changed."""
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    feature_dir = cache_path.parent / "features"
    runs = []
    for folder in folders:
        name = folder.relative_to(base).as_posix() if folder.is_relative_to(base) else folder.as_posix()
        npz = feature_dir / (hashlib.sha256(name.encode()).hexdigest()[:16] + ".npz")
        entry = cache.get(name)
        if entry is None or entry["stamp"] != stamp(folder) or not npz.exists():
            row, features, selected = analyze(folder)
            row["run"] = name
            feature_dir.mkdir(parents=True, exist_ok=True)
            np.savez(npz, features=features, selected=selected)
            entry = cache[name] = {"stamp": stamp(folder), "row": row}
            cache_path.write_text(json.dumps(cache), encoding="utf-8")  # saved per run: a killed pass resumes
        with np.load(npz) as data:
            runs.append((entry["row"], data["features"], data["selected"]))
    return runs


def pct(value: float | None, digits: int = 0) -> str:
    return "—" if value is None else f"{100 * value:.{digits}f}"


def num(value: float | None, fmt: str = "{:.2f}") -> str:
    return "—" if value is None else fmt.format(value)


def markdown(rows: Sequence[dict]) -> str:
    lines = ["# M13: diversity of the generators' candidates", "",
             f"**Rule:** within a setup (same inventory, grid and target), distances are in units of the median pairwise "
             f"distance among that setup's D2-pipeline candidates, and two designs count as distinct when they are at "
             f"least {NORM_THRESHOLD:g} units apart (half a typical D2 distance).", "",
             "`python -m brickwfc.experiments.diversity_pass` (`funnel/diversity.py`: effective number of distinct "
             "designs, Leinster-Cobbold order 1). Share = effective / designs; normalized mean distance 1 = as spread "
             "out as D2 typically is. Setups without a D2-pipeline reference: —.", "",
             "## Per generator (mean over runs with a unit)", "",
             "| generator | runs | verified per run | effective share % | normalized mean distance | "
             "selected: effective share % |", "|---|---|---|---|---|---|"]
    for generator in sorted({r["generator"] for r in rows}):
        mine = [r for r in rows if r["generator"] == generator and r.get("effective_share_norm") is not None]
        if not mine:
            lines.append(f"| {generator} | 0 | — | — | — | — |")
            continue
        mean = lambda key: (lambda v: statistics.fmean(v) if v else None)([r[key] for r in mine if r.get(key) is not None])  # noqa: E731
        lines.append(f"| {generator} | {len(mine)} | {statistics.fmean(r['verified'] for r in mine):.0f} | "
                     f"{pct(mean('effective_share_norm'), 1)} | {num(mean('mean_distance_norm'))} | "
                     f"{pct(mean('selected_effective_share_norm'), 1)} |")
    lines += ["", "## Per run", "",
              "| run | generator | setup | candidates | valid | verified | unit | share % | normalized mean distance "
              "| selected | selected share % |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['run']} | {r['generator']} | {r['setup'][:6]} | {r['candidates']} | {r['valid']} | "
                     f"{r['verified']} | {num(r['unit'], '{:.3f}')} | {pct(r['effective_share_norm'])} | "
                     f"{num(r['mean_distance_norm'])} | {r.get('selected', '—')} | {pct(r.get('selected_effective_share_norm'))} |")
    lines += ["", "## Appendix: raw profile", "",
              "Effective share % at raw feature-distance thresholds (not comparable across setups; the dedupe threshold "
              "is 0.05).", "",
              "| run | generator | raw mean distance | " + " | ".join(f"@{t:g}" for t in PROFILE) + " |",
              "|---|---|---|" + "---|" * len(PROFILE)]
    for r in rows:
        lines.append(f"| {r['run']} | {r['generator']} | {r['mean_distance']:.3f} | "
                     + " | ".join(pct(r["effective_share_at"][f"{t:g}"]) for t in PROFILE) + " |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.diversity_pass", description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=Path, default=Path("."), help="directory the run globs are relative to")
    parser.add_argument("--roots", nargs="+", default=list(DEFAULT_ROOTS), help="globs of run folders under --base")
    parser.add_argument("--cache", type=Path, default=Path("out/m13_diversity/cache.json"))
    parser.add_argument("--out", type=Path, default=Path("results/m13_diversity.json"))
    args = parser.parse_args(argv)
    runs = collect(run_folders(args.base, args.roots), args.cache, args.base)
    units = setup_units(runs)
    rows = [normalized(row, features, selected, units.get(row["setup"])) for row, features, selected in runs]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    text = markdown(rows)
    args.out.with_suffix(".md").write_text(text, encoding="utf-8")
    print(text)
    print(f"{len(rows)} runs in {len({r['setup'] for r in rows})} setups ({len(units)} with a D2 unit); "
          f"wrote {args.out} and {args.out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
