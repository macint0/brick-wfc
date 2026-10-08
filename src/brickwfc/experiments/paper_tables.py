"""M13: the paper's main table and ablation table, collected from the experiments' summary files.

    python -m brickwfc.experiments.paper_tables --out results/m13_tables.md

Nothing is run here: every number is read from a summary an experiment already wrote (``SOURCES``), so the
table is only as current as those files. Each cell is the mean over the rows of one source that match its
filter (one row per set, shape, size or build) and carries a tag naming that source. A cell whose source
file does not exist yet reads **pending**; a metric no experiment measures for that generator reads **—**.
Rows whose ``status`` is not "ok" (e.g. WFC not run for memory) are left out of every mean.

Percent columns (valid, stable, timeout) are shares of *attempted* builds, so a generator that times out
scores low on them; utilization and fill are means over the builds that *finished*; time per accepted
design is the total time of all attempts over the number of valid builds.

Sources differ in setup (plates only vs the full catalog, with or without a target shape, ...): the tag says
which experiment a number comes from, and the legend under the table describes each one. Compare numbers
within a column only when they share a tag.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Sequence

Rows = list[dict]


@dataclass(frozen=True)
class Source:
    paths: tuple[str, ...]  # the first that exists is read
    description: str
    loader: str = "json"  # "json" (a list of rows), "jsonl" (one row per line) or "brickgpt"


SOURCES: dict[str, Source] = {
    "m6": Source(("results/m6_stability_summary.json",), "M6: 1x1-2x4 plates, no inventory, 3 grid sizes"),
    "m7": Source(("results/m7_physics_summary.json",), "M7: as M6, plus physics on a table"),
    "m9": Source(("results/m9_inventory_summary.json",), "M9: 10 sets' plates as inventory"),
    "m9b": Source(("results/m9b_inventory_catalog_summary.json",), "M9b: 10 sets, full catalog, WFC capped at 30 s"),
    "m10": Source(("results/m10_style_summary.json",), "M10: 28 sets, held-out folds, learned style"),
    "m11": Source(("results/m11_shape_inventory_summary.json",), "M11: 10 sets x 5 primitive shapes"),
    "m12_balance": Source(("results/m12_balance_summary.json",), "M12: balance on/off, 2 sets"),
    "m12_connect": Source(("results/m12_connect_summary.json",), "M12: one-piece repair on/off, 2 sets"),
    "m12_demo": Source(("results/m12_demo_summary.json",), "M12 demo: spaceship from 6 sets, full pipeline"),
    "brickgpt": Source(("results/m12b_brickgpt_summary.json", "out/m12b_brickgpt/summary.json"),
                       "M12b: BrickGPT's own structures (test split), our physics", "brickgpt"),
    "proposal": Source(("results/m12b_proposal_runs.jsonl", "out/m12b_proposal/runs.jsonl"),
                       "M12b: learned proposal vs statistics, fold-0 sets", "jsonl"),
    "diversity": Source(("results/m13_diversity.json",), "M13: effective share of distinct designs among verified candidates, per alt run"),
}


def load(source: Source, root: Path) -> Rows | None:
    """The source's rows, or None if none of its files exists."""
    path = next((root / p for p in source.paths if (root / p).exists()), None)
    if path is None:
        return None
    if source.loader == "jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8"))
    if source.loader == "brickgpt":  # their structures, as rows of a "brickgpt" generator
        return [{"generator": "brickgpt", "stands": math.isfinite(o["clutch"]) if o.get("clutch") is not None else False,
                 "one_piece": o.get("clusters") == 1} for o in data["objects"]]
    return data


# Aggregations over the matching rows -------------------------------------------------------------------------


def number(value) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def mean_of(key: str, scale: float = 1.0) -> Callable[[Rows], float | None]:
    def agg(rows: Rows) -> float | None:
        values = [number(r.get(key)) for r in rows]
        values = [v for v in values if v is not None]
        return scale * sum(values) / len(values) if values else None
    return agg


def ratio(numerator: Callable[[dict], float | None], denominator: Callable[[dict], float | None],
          scale: float = 1.0) -> Callable[[Rows], float | None]:
    """sum(numerator) / sum(denominator) over rows where both are numbers (e.g. total time / accepted builds)."""
    def agg(rows: Rows) -> float | None:
        pairs = [(numerator(r), denominator(r)) for r in rows]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        total = sum(b for _, b in pairs)
        return scale * sum(a for a, _ in pairs) / total if pairs and total > 0 else None
    return agg


def field_times(key: str, weight: str | None = None) -> Callable[[dict], float | None]:
    def get(row: dict) -> float | None:
        value = number(row.get(key))
        if value is None or weight is None:
            return value
        w = number(row.get(weight))
        return None if w is None else value * w
    return get


def accepted(valid_key: str, runs_key: str | None, percent: bool = True) -> Callable[[dict], float | None]:
    """Accepted builds in a row: valid share x runs (1 run per row if ``runs_key`` is None)."""
    def get(row: dict) -> float | None:
        valid = number(row.get(valid_key))
        runs = 1.0 if runs_key is None else number(row.get(runs_key))
        if valid is None or runs is None:
            return None
        return valid / (100 if percent else 1) * runs
    return get


TIME_PER_ACCEPTED = {  # total time / accepted builds, per source layout
    "m9": ratio(field_times("time_per_run_s", "seeds"), accepted("valid_pct", "seeds")),
    "m9b": ratio(field_times("time_per_run_s", "seeds"), accepted("valid_pct", "seeds")),
    "m10": ratio(field_times("time_per_build_s", "seeds"), accepted("valid_pct", "seeds")),
    "m12_demo": ratio(field_times("seconds_per_candidate", "candidates"), accepted("valid_pct", "candidates")),
    "proposal": ratio(field_times("wall_time_s"), accepted("valid", None, percent=False)),
}
def finished_runs(*keys: str) -> Callable[[dict], float | None]:
    """Finished builds in a row: the product of ``keys`` (a percent key is divided by 100)."""
    def get(row: dict) -> float | None:
        total = 1.0
        for key in keys:
            value = number(row.get(key))
            if value is None:
                return None
            total *= value / 100 if key.endswith("_pct") else value
        return total
    return get


def weighted_by(key: str, weight: Callable[[dict], float | None]) -> Callable[[Rows], float | None]:
    """Mean of ``key`` weighted by ``weight`` per row (a per-row mean over finished builds -> a mean over all
    finished builds, so rows where nothing finished do not count as 0)."""
    return ratio(lambda r: (lambda v, w: None if v is None or w is None else v * w)(number(r.get(key)), weight(r)),
                 weight)


UTILIZATION = {  # each row's utilization is a mean over its finished builds
    "m9b": weighted_by("utilization_pct", finished_runs("finished")),
    "m9": weighted_by("utilization_pct", finished_runs("success_pct", "seeds")),
    "m12_demo": weighted_by("utilization_pct", finished_runs("built_pct", "candidates")),
    "m10": weighted_by("utilization_pct", finished_runs("finished")),
    "proposal": mean_of("utilization", 100),
}
TIMEOUT_PCT = {
    "m9b": ratio(field_times("timed_out"), field_times("seeds"), 100),
    "m10": ratio(field_times("timed_out"), field_times("seeds"), 100),
    "m12_demo": lambda rows: (lambda built: None if built is None else 100 - built)(mean_of("built_pct")(rows)),
}


@dataclass(frozen=True)
class Cell:
    source: str
    where: Mapping[str, object]  # field -> required value (or tuple of allowed values)
    agg: Callable[[Rows], float | None]
    fmt: str = "{:.1f}"


@dataclass(frozen=True)
class Value:
    text: str
    source: str | None = None


def matches(row: dict, where: Mapping[str, object]) -> bool:
    if row.get("status", "ok") != "ok":
        return False
    for key, wanted in where.items():
        allowed = wanted if isinstance(wanted, tuple) else (wanted,)
        if row.get(key) not in allowed:
            return False
    return True


def evaluate(cell: Cell | None, data: Mapping[str, Rows | None]) -> Value:
    if cell is None:
        return Value("—")
    rows = data.get(cell.source)
    if rows is None:
        return Value("pending", cell.source)
    value = cell.agg([r for r in rows if matches(r, cell.where)])
    return Value("—" if value is None else cell.fmt.format(value), cell.source)


def show(value: Value) -> str:
    return value.text if value.source is None or value.text == "—" else f"{value.text} [{value.source}]"


# The tables --------------------------------------------------------------------------------------------------

COLUMNS = ("valid %", "stable % (support rule)", "stable % (physics, table)", "utilization %", "fill / IoU %",
           "s per accepted design", "diversity (effective / verified designs, %)", "timeout %")


def generator_row(cond: Mapping[str, Mapping[str, object]], stable: Cell | None = None, fill: Cell | None = None,
                  extra: Mapping[str, Cell | None] | None = None) -> dict[str, Cell | None]:
    """Cells of a generator from its condition filter in each source (``cond[source]``)."""
    def c(source: str, agg: Callable[[Rows], float | None], fmt: str = "{:.1f}") -> Cell | None:
        return Cell(source, cond[source], agg, fmt) if source in cond else None

    first = lambda *cells: next((x for x in cells if x is not None), None)  # noqa: E731
    row = {
        "valid %": first(c("m9b", mean_of("valid_pct")), c("m9", mean_of("valid_pct")), c("m12_demo", mean_of("valid_pct")),
                         c("m10", mean_of("valid_pct")), c("proposal", mean_of("valid", 100))),
        "stable % (support rule)": stable,
        "stable % (physics, table)": first(c("m9b", mean_of("physics_any_clutch_pct")), c("m9", mean_of("physics_any_clutch_pct")),
                                           c("m12_demo", mean_of("physics_pct"))),
        "utilization %": first(*(c(s, UTILIZATION[s]) for s in ("m9b", "m9", "m12_demo", "m10", "proposal"))),
        "fill / IoU %": fill,
        "s per accepted design": first(*(c(s, TIME_PER_ACCEPTED[s], "{:.3g}") for s in ("m9b", "m9", "m12_demo", "m10", "proposal"))),
        "diversity (effective / verified designs, %)": c("diversity", mean_of("effective_share", 100), "{:.0f}"),
        "timeout %": first(*(c(s, TIMEOUT_PCT[s], "{:.0f}") for s in ("m9b", "m10", "m12_demo"))),
    }
    row.update(extra or {})
    return row


def main_table_spec() -> dict[str, dict[str, Cell | None]]:
    stable = lambda condition: Cell("m7", {"condition": condition}, mean_of("stable_pct"))  # noqa: E731
    iou = lambda condition: Cell("m11", {"condition": condition}, mean_of("mean_iou_pct"))  # noqa: E731
    return {
        "WFC + post-filter (A)": generator_row({"m9": {"condition": "A_filter"}, "diversity": {"generator": "A"}},
                                               stable("A_plain")),
        "WFC + constraints (B)": generator_row({"m9b": {"condition": "B_inventory"}, "diversity": {"generator": "B"}},
                                               stable("B_aware"), iou("B_wfc")),
        "Bottom-up (D)": generator_row({"m9b": {"condition": "D_bottom_up"}, "diversity": {"generator": "D"}},
                                       stable("D_bottom_up"), iou("D_bottom_up")),
        "Bottom-up, any offset (D2)": generator_row(
            {"m9b": {"condition": "D2_bottom_up_any_offset"}, "diversity": {"generator": "D2"}},
            Cell("m9b", {"condition": "D2_bottom_up_any_offset"}, mean_of("valid_pct")), iou("D2_bottom_up_any_offset")),
        "D2 + learned style (M10)": generator_row({"m10": {"condition": "D2_inventory", "style": "contacts"},
                                                   "diversity": {"generator": "D2_style"}}),
        "Pipeline: D2 + style + balance + one piece": generator_row(
            {"m12_demo": {"generator": "d2"}, "diversity": {"generator": "pipeline"}},
            Cell("m12_demo", {"generator": "d2"}, mean_of("valid_pct")), Cell("m12_demo", {"generator": "d2"}, mean_of("iou", 100))),
        "Pipeline with WFC as generator": generator_row(
            {"m12_demo": {"generator": "wfc"}, "diversity": {"generator": "pipeline_wfc"}},
            Cell("m12_demo", {"generator": "wfc"}, mean_of("valid_pct")), Cell("m12_demo", {"generator": "wfc"}, mean_of("iou", 100))),
        "D2 + learned proposal (M12b)": generator_row({"proposal": {"condition": "proposal_raster"},
                                                       "diversity": {"generator": "proposal"}}),
        "BrickGPT structures (their data)": {
            **{c: None for c in COLUMNS},
            "stable % (physics, table)": Cell("brickgpt", {}, mean_of("stands", 100)),
        },
    }


@dataclass(frozen=True)
class Ablation:
    constraint: str
    metric: str
    with_: Cell | None
    without: Cell | None
    note: str = ""


def ablation_spec() -> list[Ablation]:
    judge = "{:.4f}"
    return [
        Ablation("support (in WFC propagation)", "stable % (support rule)",
                 Cell("m6", {"condition": "B_aware"}, mean_of("stable_pct")),
                 Cell("m6", {"condition": "A_plain"}, mean_of("stable_pct")), "off = plain WFC, checked afterwards"),
        Ablation("inventory (in WFC propagation)", "valid %",
                 Cell("m9", {"condition": "B_inventory"}, mean_of("valid_pct")),
                 Cell("m9", {"condition": "A_filter"}, mean_of("valid_pct")), "off = post-filter"),
        Ablation("target shape", "cells outside the shape",
                 Cell("m11", {"condition": ("B_wfc", "D_bottom_up", "D2_bottom_up_any_offset")}, mean_of("cells_outside"),
                      "{:.1f}"), None, "off: not run"),
        Ablation("balance (no tip-over)", "stable % (physics, table)",
                 Cell("m12_balance", {"condition": "cube_balance"}, mean_of("physics_pct")),
                 Cell("m12_balance", {"condition": "cube_nobalance"}, mean_of("physics_pct"))),
        Ablation("one piece (connect repair)", "one piece %",
                 Cell("m12_connect", {"condition": "balance_connect"}, mean_of("connected_pct")),
                 Cell("m12_connect", {"condition": "balance"}, mean_of("connected_pct"))),
        Ablation("one piece, in the demo pipeline", "one piece %",
                 Cell("m12_demo", {"generator": "d2"}, mean_of("connected_pct")),
                 Cell("m12_demo", {"generator": "d2_no_connect"}, mean_of("connected_pct"))),
        Ablation("learned contact style", "size-matched judge",
                 Cell("m10", {"condition": "D2_inventory", "style": "contacts"}, mean_of("matched_judge"), judge),
                 Cell("m10", {"condition": "D2_inventory", "style": "uniform"}, mean_of("matched_judge"), judge),
                 "off = uniform part/color weights"),
        Ablation("learned proposal", "size-matched judge",
                 Cell("proposal", {"condition": "proposal_raster"}, mean_of("matched_judge"), judge),
                 Cell("proposal", {"condition": "stats_raster"}, mean_of("matched_judge"), judge),
                 "both raster order, statistics in both"),
        Ablation("raster visit order (control)", "size-matched judge",
                 Cell("proposal", {"condition": "stats_raster"}, mean_of("matched_judge"), judge),
                 Cell("proposal", {"condition": "stats_random"}, mean_of("matched_judge"), judge),
                 "a proposal gain must exceed this"),
    ]


def render(data: Mapping[str, Rows | None]) -> str:
    lines = ["# M13: paper tables", "",
             "Generated by `python -m brickwfc.experiments.paper_tables` from the summary files; [tag] = source "
             "(legend below), **pending** = its file does not exist yet, — = not measured.", "",
             "## Main table (one row per generator)", "",
             "| generator | " + " | ".join(COLUMNS) + " |", "|---|" + "---|" * len(COLUMNS)]
    for name, cells in main_table_spec().items():
        lines.append(f"| {name} | " + " | ".join(show(evaluate(cells.get(c), data)) for c in COLUMNS) + " |")
    lines += ["", "## Ablation (each constraint or component off)", "",
              "| component | metric | with | without | note |", "|---|---|---|---|---|"]
    for a in ablation_spec():
        lines.append(f"| {a.constraint} | {a.metric} | {show(evaluate(a.with_, data))} | "
                     f"{show(evaluate(a.without, data)) if a.without else '—'} | {a.note} |")
    lines += ["", "## Sources", "", "| tag | file | status | setup |", "|---|---|---|---|"]
    for tag, source in SOURCES.items():
        status = "found" if data.get(tag) is not None else "pending"
        lines.append(f"| {tag} | {' or '.join(f'`{p}`' for p in source.paths)} | {status} | {source.description} |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.paper_tables", description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root the source paths are relative to")
    parser.add_argument("--out", type=Path, default=Path("results/m13_tables.md"))
    args = parser.parse_args(argv)
    data = {tag: load(source, args.root) for tag, source in SOURCES.items()}
    text = render(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
