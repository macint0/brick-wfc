"""The M12e training pool as token sequences (``export_tokens --pool``): load, crop, split, report.

- **Load**: every selected model of the pool (``experiments.omr_pool``) voxelized with ``parts.CATALOG`` as it
  is at export time; the pool must have been measured on the same catalog (fingerprint check).
- **Crop**: a model larger than the token grid (64 x 64 studs, 192 plates) is cut into blocks of that size, each
  holding the parts wholly inside it, re-anchored at the origin; parts across a block edge and blocks under
  ``min_parts`` parts are dropped.
- **Split** by set number (a set's main model and alternates stay together): the demo sets are held out of
  training and exported as ``heldout`` (never used for checkpoint selection); a seeded share of the other sets
  is ``setval`` (the real-set side of the selection loss); the rest is training, in ``symmetries`` horizontal
  symmetries each.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.bricks.parts import PlacedPart
from brickwfc.bricks.tokens import MAX_XZ, MAX_Y
from brickwfc.bricks.voxelize import voxelize
from brickwfc.ldraw.mpd import flatten


@dataclass(frozen=True)
class PoolModel:
    """One selected pool model: its file, set number, and its crops (one when it fits the token grid)."""

    file: str
    set: str
    parts: int  # part instances in the file
    recognized: int
    on_grid: int  # as the pool measured it: kept parts + the accessories they hold
    crops: list[list[PlacedPart]]
    contained: int = 0  # accessories held by kept frames: on the grid, but no cells and no token of their own
    fits: bool = True  # the on-grid build fits the token grid whole (otherwise ``crops`` are blocks of it)

    @property
    def name(self) -> str:
        return self.file.removesuffix(".mpd")

    @property
    def encoded_parts(self) -> int:
        return sum(len(c) for c in self.crops)


def anchored(placed: Sequence[PlacedPart]) -> list[PlacedPart]:
    """The parts moved so that their minimum layer, z and x are 0."""
    if not placed:
        return []
    y0, z0, x0 = min(p.layer for p in placed), min(p.z for p in placed), min(p.x for p in placed)
    return [PlacedPart(p.shape, p.color, p.layer - y0, p.x - x0, p.z - z0) for p in placed]


def _inside(p: PlacedPart, y0: int, z0: int, x0: int, size_y: int, size_xz: int) -> bool:
    return (y0 <= p.layer and p.top < y0 + size_y and z0 <= p.z and p.z + p.shape.size_z <= z0 + size_xz
            and x0 <= p.x and p.x + p.shape.size_x <= x0 + size_xz)


def crops(placed: Sequence[PlacedPart], min_parts: int, size_xz: int = MAX_XZ, size_y: int = MAX_Y) -> list[list[PlacedPart]]:
    """The build as one block if its whole extent fits the token grid, else blocks of ``size_y`` plates x ``size_xz``
    studs (in (layer, z, x) block order), each holding the parts that lie wholly inside it, anchored; parts across a
    block edge and blocks under ``min_parts`` parts are dropped. Whole extents, not min corners: a turned or mirrored
    block (``tokens.symmetries``) must fit the grid too."""
    placed = anchored(placed)
    if all(_inside(p, 0, 0, 0, size_y, size_xz) for p in placed):
        return [placed] if len(placed) >= min_parts else []
    blocks: dict[tuple[int, int, int], list[PlacedPart]] = {}
    for p in placed:
        key = (p.layer // size_y, p.z // size_xz, p.x // size_xz)
        if _inside(p, key[0] * size_y, key[1] * size_xz, key[2] * size_xz, size_y, size_xz):
            blocks.setdefault(key, []).append(p)
    return [anchored(blocks[k]) for k in sorted(blocks) if len(blocks[k]) >= min_parts]


def _load(job: tuple[Path, int]) -> list[list[PlacedPart]]:
    path, min_parts = job
    placed, _ = voxelize(flatten(path.read_text(encoding="utf-8", errors="replace")))
    return crops(placed, min_parts)


def load_pool(rows: Sequence[dict], omr: Path, min_parts: int, workers: int) -> list[PoolModel]:
    """The pool's selected models (rows of ``omr_pool``'s table), voxelized and cropped, in row order."""
    jobs = [(omr / r["file"], min_parts) for r in rows]
    if workers <= 1:
        loaded = [_load(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            loaded = list(pool.map(_load, jobs, chunksize=2))
    return [PoolModel(r["file"], r["set"], r["parts"], r["recognized"], r["on_grid"], c, r.get("contained", 0),
                      r.get("fits_tokens", True)) for r, c in zip(rows, loaded)]


def split_sets(sets: Sequence[str], demo: Sequence[str], val_share: float, seed: int) -> tuple[list[str], list[str], list[str]]:
    """(training, setval, held-out demo) set numbers: demo sets present in ``sets`` are held out, then a seeded
    ``val_share`` of the rest (at least one set when ``val_share`` > 0) is validation."""
    unique = sorted(set(sets))
    held = [s for s in unique if s in set(demo)]
    rest = [s for s in unique if s not in set(demo)]
    n_val = 0 if val_share <= 0 or not rest else max(1, round(val_share * len(rest)))
    order = np.random.default_rng(seed).permutation(len(rest))
    val = sorted(rest[i] for i in order[:n_val])
    train = [s for s in rest if s not in set(val)]
    return train, val, held


def default_workers() -> int:
    return max(1, min(6, (os.cpu_count() or 3) - 2))


# Report ---------------------------------------------------------------------------------------------------


def oov_rows(models: Sequence[PoolModel], role: dict[str, str]) -> list[dict]:
    """Per model: parts, out of vocabulary (no catalog part), off the grid (recognized, not placeable), accessories
    held by frames (on the grid, exported with their frame, no token), dropped by cropping, encoded; shares of the
    model's parts."""
    rows = []
    for m in models:
        oov = m.parts - m.recognized
        rows.append({"model": m.name, "set": m.set, "role": role.get(m.set, "train"), "parts": m.parts,
                     "oov": oov, "off_grid": m.recognized - m.on_grid, "accessories": m.contained,
                     "cropped": m.on_grid - m.contained - m.encoded_parts,
                     "encoded": m.encoded_parts, "crops": len(m.crops),
                     "oov_pct": 100 * oov / m.parts if m.parts else 0.0,
                     "not_encoded_pct": 100 * (m.parts - m.encoded_parts) / m.parts if m.parts else 0.0})
    return rows


def oov_markdown(rows: Sequence[dict]) -> str:
    lines = ["| model | set | role | parts | out of vocabulary | OOV % | recognized, off grid | accessories | "
             "dropped by crop | encoded | not encoded % | crops |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (-r["oov_pct"], r["model"])):
        lines.append(f"| {r['model']} | {r['set']} | {r['role']} | {r['parts']} | {r['oov']} | {r['oov_pct']:.1f} | "
                     f"{r['off_grid']} | {r['accessories']} | {r['cropped']} | {r['encoded']} | "
                     f"{r['not_encoded_pct']:.1f} | {r['crops']} |")
    return "\n".join(lines) + "\n"


def oov_summary(rows: Sequence[dict]) -> list[str]:
    def q(key: str) -> str:
        v = np.array([r[key] for r in rows], dtype=float)
        return " / ".join(f"{np.percentile(v, p):.1f}" for p in (10, 50, 90)) if len(v) else "—"

    parts = sum(r["parts"] for r in rows)
    oov = sum(r["oov"] for r in rows)
    off = sum(r["off_grid"] for r in rows)
    acc = sum(r["accessories"] for r in rows)
    cut = sum(r["cropped"] for r in rows)
    enc = sum(r["encoded"] for r in rows)
    pct = (lambda n: f"{100 * n / parts:.1f}%") if parts else (lambda n: "0%")
    return [f"Of the pool's {parts} part instances: **{pct(oov)} out of vocabulary** (no catalog part; {oov}), "
            f"{pct(off)} recognized but off the grid (tilted, off the stud grid or overlapping; {off}), {pct(acc)} accessories "
            f"held by frames (exported with the frame, no token; {acc}), {pct(cut)} dropped by cropping "
            f"(across a block edge, or in a block under the minimum size; {cut}); **{pct(enc)} encoded** ({enc}).",
            f"Per model, 10th / 50th / 90th percentile: out of vocabulary {q('oov_pct')}%, not encoded "
            f"{q('not_encoded_pct')}%."]
