"""Export token sequences for the learned proposal model (M12b step 2).

    python -m brickwfc.experiments.export_tokens --omr ../brick-wfc/data/omr --out data/tokens

Sources (``bricks.tokens`` for the format):

- BrickGPT's StableText2Brick structures (``bricks.brickgpt``; cached in ``--brickgpt``, fetched if missing):
  the train split for training, the test split for validation. Bricks only, no colors (``NONE``).
- The 28 real sets of M10 (``--sets-file``), voxelized with the full catalog: plates, tiles and colors. They
  are split with M10's folds (``experiments.style.folds``, 4 folds, seed 0); fold ``--holdout-fold`` is held
  out of training (so the learned proposal can be compared with statistics on the same held-out sets) and
  exported as ``heldout``. Training sets are exported in ``--set-symmetries`` horizontal symmetries
  (4 turns x mirror).

With ``--pool`` (M12e; ``python -m brickwfc.experiments.export_tokens --pool results/m12e_omr_pool.json --out
data/tokens_v2 --results results/m12e_tokens.md``) the real sets are instead the selected models of an
``experiments.omr_pool`` pool, voxelized with ``parts.CATALOG`` at export time and cropped to the token grid
(``experiments.pool_tokens``), split by set number: the demo sets (``--heldout-sets``) are ``heldout``, a seeded
``--val-share`` of the other sets is ``setval`` (the real-set validation ``training/train.py`` selects on), the
rest trains in ``--set-symmetries`` symmetries. Also writes ``setval.npz`` and the per-model out-of-vocabulary
table (``--oov-results``).

Each build's own occupancy is its target mask. Writes ``vocab.json`` and ``train.npz``, ``val.npz``,
``heldout.npz`` under ``--out`` (arrays: ``header`` (N, 4), ``parts`` (P, 5) token ids, ``offsets`` (N + 1),
``masks`` (N, 1000) packed bits of the 20^3 mask, ``source``, ``fold`` (-1 for BrickGPT), ``name``), and the
dataset statistics to ``--results``. Deterministic; reruns overwrite.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.bricks import brickgpt
from brickwfc.bricks.colors import color_for_code
from brickwfc.bricks.parts import PlacedPart
from brickwfc.bricks.tokens import (HEADER, MASK_GRID, PART_TOKENS, PREFIX, Encoded, Vocab, build_vocab, encode,
                                    symmetries)
from brickwfc.bricks.voxelize import voxelize
from brickwfc.experiments.omr_pool import catalog_fingerprint
from brickwfc.experiments.pool_tokens import PoolModel, load_pool, oov_markdown, oov_rows, oov_summary, split_sets
from brickwfc.experiments.style import folds
from brickwfc.ldraw.fetch import fetch_set
from brickwfc.ldraw.mpd import flatten

GRAY = color_for_code(71)  # stand-in color for BrickGPT bricks; written as NONE
MAX_LEN = 1024  # the model's context (training/train.py), for the window statistics
SET_SHARE = 0.25  # share of training windows drawn from real sets (training/train.py default), for the report


@dataclass
class Sequences:
    """Encoded builds of one split. Each target mask is kept packed (``MASK_GRID``^3 bits in 1000 bytes, the saved
    layout) from the moment it is added, and the ``Encoded`` keeps only its header and part tokens: BrickGPT's
    ~47k unpacked 20^3 masks alone would be ~0.4 GB."""

    encoded: list[Encoded]
    source: list[str]
    fold: list[int]
    name: list[str]
    shapes: Counter  # part name -> count
    masks: list[np.ndarray] = field(default_factory=list)  # packed, one per build

    def save(self, path: Path, vocab: Vocab) -> None:
        offsets = np.zeros(len(self.encoded) + 1, dtype=np.int64)
        offsets[1:] = np.cumsum([len(e.parts) for e in self.encoded])
        parts = (np.concatenate([e.parts for e in self.encoded]) if self.encoded
                 else np.zeros((0, PART_TOKENS), dtype=np.int64))
        masks = np.stack(self.masks) if self.masks else np.zeros((0, 1000), np.uint8)
        assert len(vocab) < 2**15
        np.savez_compressed(
            path, header=(np.stack([e.header for e in self.encoded]) if self.encoded else np.zeros((0, HEADER))).astype(np.int16),
            parts=parts.astype(np.int16),
            offsets=offsets, masks=masks, source=np.array(self.source), fold=np.array(self.fold, dtype=np.int8),
            name=np.array(self.name))


def empty() -> Sequences:
    return Sequences([], [], [], [], Counter())


def add(seqs: Sequences, placed: list[PlacedPart], encoded: Encoded, source: str, fold: int, name: str) -> None:
    seqs.masks.append(np.packbits(encoded.mask.ravel()))
    seqs.encoded.append(Encoded(encoded.header, None, encoded.parts))
    seqs.source.append(source)
    seqs.fold.append(fold)
    seqs.name.append(name)
    seqs.shapes.update(p.shape.part.name for p in placed)


def load_npz(path: Path) -> dict[str, np.ndarray]:
    """An exported split; ``masks`` unpacked to (N, 20, 20, 20) bool."""
    with np.load(path) as data:
        out = {k: data[k] for k in data.files}
    out["masks"] = np.unpackbits(out["masks"], axis=1)[:, : MASK_GRID**3].reshape(-1, MASK_GRID, MASK_GRID, MASK_GRID).astype(bool)
    return out


# BrickGPT -------------------------------------------------------------------------------------------------


def _encode_structures(args: tuple[list[str], list[str], list[str]]) -> list[tuple[str, list, Encoded | None]]:
    """Worker: (structure id, placed parts, encoding or None if malformed) per BrickGPT text."""
    ids, texts, colors = args
    vocab = build_vocab(colors)
    out = []
    for structure_id, text in zip(ids, texts):
        bricks = brickgpt.parse(text)
        if not bricks or brickgpt.overlaps(bricks):
            out.append((structure_id, [], None))
            continue
        placed = brickgpt.to_placed(bricks, GRAY)
        out.append((structure_id, placed, encode(placed, vocab, "brickgpt", colorless=True)))
    return out


def brickgpt_split(split: str, data_dir: Path, colors: list[str], workers: int, chunk: int = 500) -> tuple[Sequences, int]:
    """Encoded structures of a BrickGPT split, in file order; also the number skipped as malformed."""
    path = brickgpt.cache_path(split, data_dir)
    if not path.exists():  # fetch_rows always asks the server for the row count, so only call it when needed
        brickgpt.fetch_rows(split, data_dir)
    rows = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    jobs = [([r["structure_id"] for r in rows[i : i + chunk]], [r["bricks"] for r in rows[i : i + chunk]], colors)
            for i in range(0, len(rows), chunk)]
    seqs, skipped = empty(), 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for results in pool.map(_encode_structures, jobs):
            for structure_id, placed, encoded in results:
                if encoded is None:
                    skipped += 1
                else:
                    add(seqs, placed, encoded, "brickgpt", -1, structure_id)
    return seqs, skipped


# Real sets ------------------------------------------------------------------------------------------------


def load_sets(sets: Sequence[str], omr: Path) -> dict[str, list[PlacedPart]]:
    return {s: voxelize(flatten(fetch_set(s, omr).read_text(encoding="utf-8", errors="replace")))[0] for s in sets}


def set_splits(models: dict[str, list[PlacedPart]], fold_of: dict[str, int], holdout: int, count: int,
               vocab: Vocab) -> tuple[Sequences, Sequences]:
    """(training sequences: every symmetry of the other folds' sets, held-out sequences: fold ``holdout``)."""
    train, held = empty(), empty()
    for number, placed in models.items():
        if fold_of[number] == holdout:
            add(held, placed, encode(placed, vocab, "set"), "set", fold_of[number], number)
            continue
        for k, variant in enumerate(symmetries(placed, count)):
            add(train, variant, encode(variant, vocab, "set"), "set", fold_of[number], f"{number}/sym{k}")
    return train, held


def merge(a: Sequences, b: Sequences) -> Sequences:
    return Sequences(a.encoded + b.encoded, a.source + b.source, a.fold + b.fold, a.name + b.name, a.shapes + b.shapes,
                     a.masks + b.masks)


# Report ---------------------------------------------------------------------------------------------------


def windows(parts: int, max_len: int = MAX_LEN) -> int:
    """Training windows needed to cover a build of ``parts`` parts (EOS included) with half-overlapping windows."""
    per = (max_len - PREFIX - 1) // PART_TOKENS
    return 1 if parts <= per else 1 + -(-(parts - per) // (per // 2))


def report(splits: dict[str, Sequences], vocab: Vocab, holdout_sets: list[str], symmetries_n: int, skipped: dict[str, int],
           fold_seed: int, n_folds: int, holdout: int) -> str:
    lines = ["# M12b step 2: token dataset", "", *sequence_table(splits, vocab)]
    train = splits["train"]
    natural = set_share_of(train)
    lines += ["", f"Skipped as malformed (overlapping bricks or empty): "
              + ", ".join(f"{k} {v}" for k, v in skipped.items()) + ".", "",
              "## Real sets: folds, symmetries, oversampling", "",
              f"- Folds: M10's (`experiments.style.folds`, {n_folds} folds, seed {fold_seed}). **Held out (fold {holdout}):** "
              + ", ".join(holdout_sets) + ". Not in training; exported once as `heldout.npz`.",
              f"- Training sets: each in **{symmetries_n} horizontal symmetries** (4 quarter turns x mirror along x).",
              f"- Oversampling: real sets are {100 * natural:.2f}% of training parts (after symmetries); `training/train.py` "
              f"draws {100 * SET_SHARE:.0f}% of training windows from them (`--set-share`), "
              f"**{SET_SHARE / natural if natural else 0:.1f}x** their natural share.", "",
              *part_types(train, vocab)]
    return "\n".join(lines) + "\n"


def sequence_table(splits: dict[str, Sequences], vocab: Vocab) -> list[str]:
    """The format line, the vocabulary size and per split / source sequence statistics."""
    lines = ["`python -m brickwfc.experiments.export_tokens` (format: `bricks/tokens.py`). One part = 5 tokens "
             "(Y Z X SHAPE COLOR), raster order (layer, z, x); prefix = 4 header tokens + 64 mask patches "
             f"(20^3 coarse mask, 5^3 patches); context {MAX_LEN} tokens = {(MAX_LEN - PREFIX - 1) // PART_TOKENS} parts.", "",
             f"Vocabulary: **{len(vocab)} tokens** ({len(vocab.shape_ids())} shapes, {len(vocab.color_ids())} colors).", "",
             "| split | source | sequences | parts | part tokens | mean parts | p50 | p90 | max | windows @1024 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for split, seqs in splits.items():
        for source in sorted(set(seqs.source)):
            sizes = np.array([len(e.parts) for e, s in zip(seqs.encoded, seqs.source) if s == source])
            lines.append(f"| {split} | {source} | {len(sizes)} | {sizes.sum()} | {sizes.sum() * PART_TOKENS} | "
                         f"{sizes.mean():.1f} | {np.percentile(sizes, 50):.0f} | {np.percentile(sizes, 90):.0f} | "
                         f"{sizes.max()} | {sum(windows(int(n)) for n in sizes)} |")
    return lines


def set_share_of(seqs: Sequences) -> float:
    """Real sets' share of a split's parts."""
    total = sum(len(e.parts) for e in seqs.encoded)
    return sum(len(e.parts) for e, s in zip(seqs.encoded, seqs.source) if s == "set") / total if total else 0.0


def part_types(train: Sequences, vocab: Vocab) -> list[str]:
    """Part counts per source and the real sets' colors in the training split."""
    lines = ["## Part types (training split)", "", "| part | brickgpt | set |", "|---|---|---|"]
    by_source = {src: Counter() for src in ("brickgpt", "set")}
    for e, src in zip(train.encoded, train.source):
        by_source[src].update(vocab.tokens[int(t)][2:].removesuffix("_r90") for t in e.parts[:, 3])
    names = sorted(set(by_source["brickgpt"]) | set(by_source["set"]),
                   key=lambda n: -(by_source["brickgpt"][n] + by_source["set"][n]))
    lines += [f"| {n} | {by_source['brickgpt'][n]} | {by_source['set'][n]} |" for n in names]
    colors = Counter(vocab.tokens[int(t)][2:] for e, s in zip(train.encoded, train.source) if s == "set" for t in e.parts[:, 4])
    return lines + ["", "## Colors (training sets)", "", ", ".join(f"{c} {n}" for c, n in colors.most_common())]


# Pool (M12e) ----------------------------------------------------------------------------------------------

ROLES = {"train": 0, "setval": 1, "heldout": 2}  # the ``fold`` column of pool exports


def pool_splits(models: Sequence[PoolModel], role: dict[str, str], count: int, vocab: Vocab) -> dict[str, Sequences]:
    """Training (every symmetry), setval and heldout (as they are) sequences of the pool, by each set's role.
    Sequences are named ``<model>/sym<k>``, or ``<model>/c<j>/sym<k>`` for the crops of a large model."""
    out = {name: empty() for name in ROLES}
    for m in models:
        split = role.get(m.set, "train")
        for j, crop in enumerate(m.crops):
            stem = m.name if len(m.crops) == 1 else f"{m.name}/c{j}"
            variants = symmetries(crop, count) if split == "train" else [crop]
            for k, variant in enumerate(variants):
                add(out[split], variant, encode(variant, vocab, "set"), "set", ROLES[split], f"{stem}/sym{k}")
    return out


def pool_report(splits: dict[str, Sequences], vocab: Vocab, pool: dict, sets: tuple[list[str], list[str], list[str]],
                models: Sequence[PoolModel], oov: list[dict], args: argparse.Namespace, skipped: dict[str, int]) -> str:
    train_sets, val_sets, held_sets = sets
    natural = set_share_of(splits["train"])
    missing_demo = [s for s in args.heldout_sets if s not in held_sets]
    crops = [m for m in models if not m.fits]
    lines = ["# M12e: token dataset for proposal model v2", "", *sequence_table(splits, vocab), "",
             "Skipped as malformed (BrickGPT): " + ", ".join(f"{k} {v}" for k, v in skipped.items()) + ".", "",
             "## Sources and splits", "",
             f"- Pool: `{args.pool.as_posix()}` (catalog `{pool['catalog']}`, {pool['catalog_parts']} parts; thresholds "
             f"{pool['thresholds']}): **{len(models)} models from {len(set(m.set for m in models))} sets**. The "
             f"vocabulary is built from `parts.CATALOG` at export time: {len(vocab.shape_ids())} shape tokens.",
             "- BrickGPT's splits as before: train in training, test as `val`.",
             f"- **Held out** (`heldout.npz`, never trained on, never used for selection; the demo sets): "
             + (", ".join(held_sets) or "none")
             + (f". Not in the pool, so not exported: {', '.join(missing_demo)}" if missing_demo else "") + ".",
             f"- **Set validation** (`setval.npz`, the real-set half of the selection loss in `training/train.py`): "
             f"{len(val_sets)} sets, a seeded {100 * args.val_share:.0f}% of the rest (seed {args.val_seed}): "
             + ", ".join(val_sets) + ".",
             f"- Training: {len(train_sets)} sets, each crop in **{args.set_symmetries} horizontal symmetries**. A set's "
             "main model and alternates are always in the same split.",
             f"- Cropping: {len(crops)} models do not fit the token grid (64 x 64 studs x 192 plates) and are cut into "
             f"blocks of that size, each keeping the parts wholly inside it (parts across a block edge and blocks under "
             f"{args.min_crop_parts} parts dropped); blocks kept per model: "
             + (", ".join(f"{m.name} ({len(m.crops)})" for m in crops) or "none") + ".",
             f"- Real sets are {100 * natural:.1f}% of training parts (after symmetries); `training/train.py` draws "
             f"`--set-share` of training windows from them.", "",
             "## Out of vocabulary", "", *oov_summary(oov), "",
             f"Per model: `{args.oov_results.as_posix()}`.", "", *part_types(splits["train"], vocab)]
    return "\n".join(lines) + "\n"


def export_pool(args: argparse.Namespace) -> str:
    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    if pool["catalog"] != catalog_fingerprint():
        raise SystemExit(f"{args.pool} was measured on catalog {pool['catalog']}, the catalog is now "
                         f"{catalog_fingerprint()}: rerun python -m brickwfc.experiments.omr_pool first")
    rows = [r for r in pool["models"] if r["selected"] == "yes"]
    models = load_pool(rows, args.omr, args.min_crop_parts, args.workers)
    sets = split_sets([m.set for m in models], args.heldout_sets, args.val_share, args.val_seed)
    role = {s: "train" for s in sets[0]} | {s: "setval" for s in sets[1]} | {s: "heldout" for s in sets[2]}
    colors = sorted({p.color.name for m in models for crop in m.crops for p in crop})
    vocab = build_vocab(colors)
    set_part = pool_splits(models, role, args.set_symmetries, vocab)
    gpt_train, skipped_train = brickgpt_split("train", args.brickgpt, colors, args.workers)
    gpt_val, skipped_val = brickgpt_split("test", args.brickgpt, colors, args.workers)
    splits = {"train": merge(gpt_train, set_part["train"]), "val": gpt_val, "setval": set_part["setval"],
              "heldout": set_part["heldout"]}
    args.out.mkdir(parents=True, exist_ok=True)
    vocab.save(args.out / "vocab.json")
    for name, seqs in splits.items():
        seqs.save(args.out / f"{name}.npz", vocab)
    # What the tokens were built from, so a training run can check it against the code it runs with.
    (args.out / "export.json").write_text(json.dumps(
        {"catalog": pool["catalog"], "catalog_parts": pool["catalog_parts"], "pool": args.pool.as_posix(),
         "sets": {"train": len(sets[0]), "setval": sets[1], "heldout": sets[2]},
         "set_share_of_train_parts": round(set_share_of(splits["train"]), 4),
         "sequences": {k: len(v.encoded) for k, v in splits.items()}}, indent=1), encoding="utf-8")
    oov = oov_rows(models, role)
    args.oov_results.parent.mkdir(parents=True, exist_ok=True)
    args.oov_results.write_text("# M12e: out-of-vocabulary share per pool model\n\n" + "\n".join(oov_summary(oov))
                                + "\n\n" + oov_markdown(oov), encoding="utf-8")
    return pool_report(splits, vocab, pool, sets, models, oov, args, {"train": skipped_train, "test": skipped_val})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.experiments.export_tokens", description=__doc__.splitlines()[0])
    parser.add_argument("--brickgpt", type=Path, default=brickgpt.DATA_DIR, help="BrickGPT cache directory")
    parser.add_argument("--omr", type=Path, default=Path("data/omr"))
    parser.add_argument("--sets-file", type=Path, default=Path("results/sets_selection.json"))
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--fold-seed", type=int, default=0)
    parser.add_argument("--holdout-fold", type=int, default=0)
    parser.add_argument("--set-symmetries", type=int, default=8, choices=range(1, 9))
    parser.add_argument("--out", type=Path, default=Path("data/tokens"))
    parser.add_argument("--results", type=Path, default=Path("results/m12b_tokens.md"))
    parser.add_argument("--workers", type=int, default=max(1, min(3, (os.cpu_count() or 3) - 2)))
    pool = parser.add_argument_group("pool (M12e): replaces --sets-file and the folds")
    pool.add_argument("--pool", type=Path, help="an experiments.omr_pool pool, e.g. results/m12e_omr_pool.json")
    pool.add_argument("--heldout-sets", nargs="*", default=["6378-1", "31048-1"], help="demo sets held out")
    pool.add_argument("--val-share", type=float, default=0.05, help="share of the other pool sets in setval")
    pool.add_argument("--val-seed", type=int, default=0)
    pool.add_argument("--min-crop-parts", type=int, default=20, help="smallest crop of a large model kept")
    pool.add_argument("--oov-results", type=Path, default=Path("results/m12e_tokens_oov.md"))
    args = parser.parse_args(argv)

    if args.pool:
        text = export_pool(args)
        args.results.parent.mkdir(parents=True, exist_ok=True)
        args.results.write_text(text, encoding="utf-8")
        print(text)
        return 0

    sets = json.loads(args.sets_file.read_text(encoding="utf-8"))["selected"]
    fold_of = {s: k for k, members in enumerate(folds(sets, args.folds, args.fold_seed)) for s in members}
    models = load_sets(sets, args.omr)
    colors = sorted({p.color.name for placed in models.values() for p in placed})
    vocab = build_vocab(colors)
    set_train, held = set_splits(models, fold_of, args.holdout_fold, args.set_symmetries, vocab)
    gpt_train, skipped_train = brickgpt_split("train", args.brickgpt, colors, args.workers)
    gpt_val, skipped_val = brickgpt_split("test", args.brickgpt, colors, args.workers)
    splits = {"train": merge(gpt_train, set_train), "val": gpt_val, "heldout": held}

    args.out.mkdir(parents=True, exist_ok=True)
    vocab.save(args.out / "vocab.json")
    for name, seqs in splits.items():
        seqs.save(args.out / f"{name}.npz", vocab)
    holdout_sets = [s for s in sets if fold_of[s] == args.holdout_fold]
    text = report(splits, vocab, holdout_sets, args.set_symmetries, {"train": skipped_train, "test": skipped_val},
                  args.fold_seed, args.folds, args.holdout_fold)
    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
