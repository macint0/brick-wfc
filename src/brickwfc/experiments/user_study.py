"""M13 user study: pairwise preferences between builds of two (or more) generators, and a Bradley-Terry fit.

    python -m brickwfc.experiments.user_study pairs out/run_d2 out/run_wfc --n 30 --seed 0 --out out/study
    python -m brickwfc.experiments.user_study fit --key out/study/key.csv --votes votes.csv --out out/study

``pairs`` takes the build previews (``build_*.png``, as ``alt`` writes them) of each folder and writes
``pair_001.png``, ... with two builds side by side, labelled 1 (left) and 2 (right) only. Which generator is
left is drawn at random (seeded), and the pairs are shuffled, so neither position nor order gives the source
away. ``key.csv`` (keep it hidden from raters) maps each pair to the two files and their generators;
``votes_template.csv`` has one row per pair for a rater to fill in ``winner`` with 1, 2 or tie.

``fit`` reads any number of filled-in vote files (one row per pair and rater: ``pair, winner[, rater]``) and
fits the Bradley-Terry model P(i beats j) = 1 / (1 + exp(s_j - s_i)) by maximum likelihood (scipy), with a
tie counted as half a win each way and a small Gaussian prior on the strengths (``--prior``) that keeps
them finite when one side always wins and fixes their scale (they are centered to mean 0). Strengths are
fitted per generator (``--level generator``, the paper's question) or per build (``--level build``).
Reports each strength with a 95% interval from the curvature at the optimum, and the probability that each
item beats the first one. Writes ``bt_<level>.json`` and ``bt_<level>.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import minimize

GAP = 24
LABEL_H = 36


def label_font() -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=28)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


# Pairs -------------------------------------------------------------------------------------------------


def previews(folder: Path) -> list[Path]:
    """A run folder's build previews, in name order."""
    return sorted(folder.glob("build_*.png"))


def pair_image(left: Path, right: Path) -> Image.Image:
    """The two previews side by side on white, labelled 1 and 2 above them."""
    images = [Image.open(p).convert("RGB") for p in (left, right)]
    width = max(i.width for i in images)
    height = max(i.height for i in images)
    canvas = Image.new("RGB", (2 * width + GAP, height + LABEL_H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    font = label_font()
    for k, image in enumerate(images):
        x = k * (width + GAP)
        canvas.paste(image, (x + (width - image.width) // 2, LABEL_H + (height - image.height) // 2))
        draw.text((x + width // 2, LABEL_H // 2), str(k + 1), fill=(0, 0, 0), font=font, anchor="mm")
    draw.line([(width + GAP // 2, LABEL_H), (width + GAP // 2, height + LABEL_H)], fill=(200, 200, 200), width=2)
    return canvas


def plan_pairs(folders: Sequence[Path], labels: Sequence[str], n: int, rng: np.random.Generator) -> list[dict]:
    """``n`` pairs of builds from two different generators, drawn without repeats; sides and order random.
    With more than two folders, every pair of generators is used about equally often."""
    builds = {label: previews(folder) for label, folder in zip(labels, folders)}
    for label, files in builds.items():
        if not files:
            raise ValueError(f"no build_*.png previews for {label}")
    generator_pairs = [(a, b) for i, a in enumerate(labels) for b in labels[i + 1 :]]
    pools = {(a, b): [(x, y) for x, y in product(builds[a], builds[b])] for a, b in generator_pairs}
    for key in pools:
        pools[key] = [pools[key][i] for i in rng.permutation(len(pools[key]))]
    pairs = []
    while len(pairs) < n and any(pools.values()):
        for a, b in generator_pairs:
            if len(pairs) == n or not pools[(a, b)]:
                continue
            x, y = pools[(a, b)].pop()
            if rng.random() < 0.5:
                pairs.append({"left_file": x, "left_generator": a, "right_file": y, "right_generator": b})
            else:
                pairs.append({"left_file": y, "left_generator": b, "right_file": x, "right_generator": a})
    order = rng.permutation(len(pairs))
    return [{"pair": f"pair_{i + 1:03d}", **pairs[j]} for i, j in enumerate(order)]


def write_pairs(folders: Sequence[Path], labels: Sequence[str], n: int, seed: int, out: Path) -> list[dict]:
    pairs = plan_pairs(folders, labels, n, np.random.default_rng(seed))
    out.mkdir(parents=True, exist_ok=True)
    for p in pairs:
        pair_image(p["left_file"], p["right_file"]).save(out / f"{p['pair']}.png")
    with (out / "key.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, ["pair", "left_generator", "left_file", "right_generator", "right_file"])
        writer.writeheader()
        writer.writerows({**p, "left_file": str(p["left_file"]), "right_file": str(p["right_file"])} for p in pairs)
    with (out / "votes_template.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pair", "winner", "rater"])
        writer.writerows([p["pair"], "", ""] for p in pairs)
    return pairs


# Bradley-Terry ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Comparison:
    i: int  # item indices
    j: int
    w: float  # wins of i over j in this comparison: 1, 0, or 0.5 for a tie


@dataclass(frozen=True)
class BTResult:
    items: list[str]
    strengths: np.ndarray  # centered to mean 0
    stderr: np.ndarray
    comparisons: int

    def p_beats(self, a: int, b: int) -> float:
        return float(1 / (1 + math.exp(self.strengths[b] - self.strengths[a])))


def fit_bradley_terry(comparisons: Sequence[Comparison], n_items: int, prior: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    """(strengths, standard errors) maximizing sum w log s(d) + (1 - w) log s(-d) - prior/2 |s|^2, d = s_i - s_j."""
    i = np.array([c.i for c in comparisons], dtype=np.int64)
    j = np.array([c.j for c in comparisons], dtype=np.int64)
    w = np.array([c.w for c in comparisons], dtype=float)

    def objective(s: np.ndarray) -> tuple[float, np.ndarray]:
        d = s[i] - s[j]
        p = 1 / (1 + np.exp(-d))
        nll = -(w * -np.logaddexp(0, -d) + (1 - w) * -np.logaddexp(0, d)).sum() + prior / 2 * (s @ s)
        g = w - p  # d(log-likelihood)/dd
        grad = prior * s - np.bincount(i, g, n_items) + np.bincount(j, g, n_items)
        return float(nll), grad

    result = minimize(objective, np.zeros(n_items), jac=True, method="L-BFGS-B")
    s = result.x - result.x.mean()
    # Curvature at the optimum: the Fisher information of the likelihood plus the prior.
    p = 1 / (1 + np.exp(-(s[i] - s[j])))
    v = p * (1 - p)
    hessian = prior * np.eye(n_items)
    np.add.at(hessian, (i, i), v)
    np.add.at(hessian, (j, j), v)
    np.add.at(hessian, (i, j), -v)
    np.add.at(hessian, (j, i), -v)
    stderr = np.sqrt(np.clip(np.diag(np.linalg.inv(hessian)), 0, None))
    return s, stderr


def read_key(path: Path) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["pair"]: row for row in csv.DictReader(f)}


def read_votes(paths: Sequence[Path]) -> list[dict]:
    votes = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as f:
            votes += [row for row in csv.DictReader(f) if (row.get("winner") or "").strip()]
    return votes


def comparisons_from(votes: Sequence[dict], key: dict[str, dict], level: str) -> tuple[list[str], list[Comparison]]:
    """Items (generators or build files) and one comparison per vote, left item first."""
    column = "generator" if level == "generator" else "file"
    items: list[str] = sorted({key[v["pair"]][f"{side}_{column}"] for v in votes for side in ("left", "right")})
    index = {name: k for k, name in enumerate(items)}
    outcome = {"1": 1.0, "left": 1.0, "2": 0.0, "right": 0.0, "tie": 0.5}
    found = []
    for v in votes:
        row, winner = key[v["pair"]], v["winner"].strip().lower()
        if winner not in outcome:
            raise ValueError(f"{v['pair']}: winner must be 1, 2 or tie, got {v['winner']!r}")
        found.append(Comparison(index[row[f"left_{column}"]], index[row[f"right_{column}"]], outcome[winner]))
    return items, found


def fit(votes: Sequence[dict], key: dict[str, dict], level: str = "generator", prior: float = 0.01) -> BTResult:
    items, comps = comparisons_from(votes, key, level)
    strengths, stderr = fit_bradley_terry(comps, len(items), prior)
    return BTResult(items, strengths, stderr, len(comps))


def report(result: BTResult, level: str) -> str:
    lines = [f"Bradley-Terry fit per {level}: {result.comparisons} votes. P(beats {result.items[0]}) is against the "
             f"first item.", "", f"| {level} | strength | 95% interval | P(beats {result.items[0]}) |", "|---|---|---|---|"]
    order = np.argsort(-result.strengths)
    for k in order:
        s, e = result.strengths[k], result.stderr[k]
        lines.append(f"| {result.items[k]} | {s:+.3f} | [{s - 1.96 * e:+.3f}, {s + 1.96 * e:+.3f}] | {result.p_beats(k, 0):.2f} |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.user_study", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pairs", help="write pair images and the hidden key")
    p.add_argument("folders", nargs="+", type=Path, help="run folders with build_*.png (at least two)")
    p.add_argument("--labels", nargs="+", help="generator names (default: folder names)")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, default=Path("out/study"))
    f = sub.add_parser("fit", help="fit Bradley-Terry strengths from filled-in votes")
    f.add_argument("--key", type=Path, required=True)
    f.add_argument("--votes", type=Path, nargs="+", required=True)
    f.add_argument("--level", choices=["generator", "build"], default="generator")
    f.add_argument("--prior", type=float, default=0.01, help="precision of the Gaussian prior on the strengths")
    f.add_argument("--out", type=Path, default=Path("out/study"))
    args = parser.parse_args(argv)
    if args.command == "pairs":
        if len(args.folders) < 2:
            parser.error("pairs needs at least two folders")
        labels = args.labels or [folder.name for folder in args.folders]
        if len(labels) != len(args.folders) or len(set(labels)) != len(labels):
            parser.error("give one distinct label per folder")
        pairs = write_pairs(args.folders, labels, args.n, args.seed, args.out)
        print(f"wrote {len(pairs)} pairs, key.csv (hidden) and votes_template.csv to {args.out}")
        return 0
    result = fit(read_votes(args.votes), read_key(args.key), args.level, args.prior)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"bt_{args.level}.json").write_text(json.dumps(
        {"items": result.items, "strengths": result.strengths.tolist(), "stderr": result.stderr.tolist(),
         "votes": result.comparisons}, indent=2), encoding="utf-8")
    text = report(result, args.level)
    (args.out / f"bt_{args.level}.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
