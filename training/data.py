"""Training windows from the exported token data (``experiments/export_tokens.py``). numpy only, so it is
tested without PyTorch and shared by ``train.py``.

A window is one model input: the 4 header tokens, the 64 mask patches, and up to ``max_parts`` consecutive
parts of one build (5 tokens each), then EOS if the window reaches the build's end. A window that does not
start at the build's first part has ``CONT`` instead of ``BOS``. With probability ``mask_drop`` the target
is dropped (``NOMASK``, zero patches), so the model also proposes without a target.

Translation jitter (``Sampler(jitter=...)``): a training window's build is moved by a random whole number of
coarse mask voxels along Z and X (never Y), its part tokens and its mask patches together. A coarse voxel is
``s`` studs (``s`` = the header's ``SCALE``), and the shift keeps the build inside the 20^3 mask grid and the
64-stud token grid, so the scale is unchanged and the max-pooled mask moves by whole voxels: the shifted window
is exactly what ``bricks.tokens.encode`` gives for the shifted build. Builds at scale 1 also move towards the
origin when they do not touch it (BrickGPT's structures); larger builds move only away from it, since moving
them towards the origin could lower the scale ``encode`` picks.

Layout of ``ids`` (length ``PREFIX + 5 * parts (+ 1)``): header ids, then ``PAD`` in the 64 mask slots (the
model puts the patch embeddings there), then the part tokens. The loss is on every position from ``PREFIX``
on (the first part's Y is predicted from the last mask slot).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

HEADER, MASK_PATCHES, PATCH, MASK_GRID, PART_TOKENS = 4, 64, 5, 20, 5
PREFIX = HEADER + MASK_PATCHES
PATCH_BITS = PATCH**3


def max_parts(max_len: int) -> int:
    """Parts per window so that the window and its EOS fit in ``max_len`` positions."""
    return (max_len - PREFIX - 1) // PART_TOKENS


def unpack(packed: np.ndarray) -> np.ndarray:
    """(N, 20, 20, 20) (y, z, x) uint8 masks from (N, 1000) packed ones."""
    return np.unpackbits(packed, axis=1)[:, : MASK_GRID**3].reshape(-1, MASK_GRID, MASK_GRID, MASK_GRID)


def patches(packed: np.ndarray, shift: tuple[int, int] = (0, 0)) -> np.ndarray:
    """(64, 125) float32 patch vectors from a packed 20^3 mask (``bricks.tokens.patches`` layout), the mask moved
    by ``shift`` (z, x) coarse voxels (into empty voxels only: ``Split.shift_ranges``)."""
    mask = unpack(packed[None])[0]
    if shift != (0, 0):
        mask = np.roll(mask, shift, axis=(1, 2))
    n = MASK_GRID // PATCH
    blocks = mask.reshape(n, PATCH, n, PATCH, n, PATCH).transpose(0, 2, 4, 1, 3, 5)
    return blocks.reshape(MASK_PATCHES, PATCH_BITS).astype(np.float32)


@dataclass
class Vocab:
    tokens: list[str]

    @classmethod
    def load(cls, path: Path) -> "Vocab":
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["tokens"])

    def id(self, token: str) -> int:
        return self.tokens.index(token)


class Split:
    """One exported split (``train.npz``, ``val.npz`` or ``heldout.npz``)."""

    def __init__(self, path: Path, vocab: Vocab) -> None:
        with np.load(path) as data:
            self.header = data["header"].astype(np.int64)
            self.parts = data["parts"].astype(np.int64)
            self.offsets = data["offsets"]
            self.masks = data["masks"]
            self.source = data["source"]
            self.name = data["name"]
        self.pad, self.bos, self.cont, self.eos = (vocab.id(t) for t in ("PAD", "BOS", "CONT", "EOS"))
        self.mask, self.nomask = vocab.id("MASK"), vocab.id("NOMASK")
        # Z and X tokens are consecutive ids (Z0..Z{n-1}), so moving a part by d studs adds d to their ids.
        self.max_xz = sum(t[0] == "Z" and t[1:].isdigit() for t in vocab.tokens)
        for axis in "ZX":
            first = vocab.id(f"{axis}0")
            if vocab.tokens[first : first + self.max_xz] != [f"{axis}{i}" for i in range(self.max_xz)]:
                raise ValueError(f"{axis} tokens are not consecutive in the vocabulary")
        self.scale = np.array([int(vocab.tokens[t].removeprefix("SCALE_")) for t in self.header[:, 2]], dtype=np.int64)

    def __len__(self) -> int:
        return len(self.header)

    def size(self, i: int) -> int:
        """Parts in build ``i``."""
        return int(self.offsets[i + 1] - self.offsets[i])

    def shift_ranges(self, indices: Sequence[int], chunk: int = 4096) -> np.ndarray:
        """(len(indices), 4) int: the lowest and highest Z shift, then X shift, in coarse voxels, that keep each
        build inside the mask grid and the token grid at its scale (all 0 for an empty mask)."""
        indices = np.asarray(indices, dtype=np.int64)
        out = np.zeros((len(indices), 4), dtype=np.int64)
        for a in range(0, len(indices), chunk):
            at = indices[a : a + chunk]
            columns = unpack(self.masks[at]).any(axis=1)  # (n, z, x): occupied at any height
            s = self.scale[at]
            limit = np.minimum(MASK_GRID, self.max_xz // s)  # voxels per axis inside both grids
            for axis, occupied in enumerate((columns.any(axis=2), columns.any(axis=1))):
                first = occupied.argmax(axis=1)
                last = MASK_GRID - 1 - occupied[:, ::-1].argmax(axis=1)
                empty = ~occupied.any(axis=1)
                out[a : a + chunk, 2 * axis] = np.where(empty | (s > 1), 0, -first)
                out[a : a + chunk, 2 * axis + 1] = np.where(empty, 0, limit - 1 - last)
        return out

    def window(self, i: int, start: int, count: int, drop_mask: bool,
               shift: tuple[int, int] = (0, 0)) -> tuple[np.ndarray, np.ndarray]:
        """(ids, patches) of build ``i`` from part ``start``, at most ``count`` parts, the build moved by ``shift``
        (z, x) coarse voxels (within ``shift_ranges``)."""
        n = self.size(i)
        end = min(n, start + count)
        head = self.header[i].copy()
        head[0] = self.bos if start == 0 else self.cont
        if drop_mask:
            head[3] = self.nomask
        rows = self.parts[self.offsets[i] + start : self.offsets[i] + end]
        if shift != (0, 0):
            rows = rows + np.array([0, shift[0], shift[1], 0, 0]) * self.scale[i]
        tail = [self.eos] if end == n else []
        ids = np.concatenate([head, np.full(MASK_PATCHES, self.pad), rows.ravel(), tail]).astype(np.int64)
        mask = np.zeros((MASK_PATCHES, PATCH_BITS), np.float32) if drop_mask else patches(self.masks[i], shift)
        return ids, mask

    def windows_of(self, i: int, count: int) -> int:
        """How many window starts build ``i`` has (1 if it fits in one window)."""
        return max(1, self.size(i) - count + 1)


def collate(items: list[tuple[np.ndarray, np.ndarray]], pad: int) -> tuple[np.ndarray, np.ndarray]:
    """Batch of windows: (B, L) ids padded with ``pad`` at the end, (B, 64, 125) patches."""
    length = max(len(ids) for ids, _ in items)
    ids = np.full((len(items), length), pad, dtype=np.int64)
    for b, (row, _) in enumerate(items):
        ids[b, : len(row)] = row
    return ids, np.stack([m for _, m in items])


class Sampler:
    """Random training windows: a source is drawn (real sets with probability ``set_share``), then a build
    of that source with probability proportional to its number of windows, then a start uniformly; for the
    sources in ``jitter``, then a shift along Z and X, each uniform over the build's ``shift_ranges``."""

    def __init__(self, split: Split, max_len: int, set_share: float, mask_drop: float,
                 exclude: Sequence[int] = (), jitter: Sequence[str] = ()) -> None:
        """``exclude``: build indices never sampled (held out for validation). ``jitter``: the sources
        (``brickgpt``, ``set``) whose windows are moved at random; none by default, which draws nothing extra, so
        the batches are those of a sampler without jitter."""
        self.split, self.count, self.mask_drop = split, max_parts(max_len), mask_drop
        weights = np.array([min(split.size(i), 10 * self.count) / self.count + 1 for i in range(len(split))])
        excluded = np.zeros(len(split), dtype=bool)
        excluded[list(exclude)] = True
        self.pools = []
        for source in ("brickgpt", "set"):
            members = np.flatnonzero((split.source == source) & ~excluded)
            if len(members):
                self.pools.append((source, members, weights[members] / weights[members].sum()))
        shares = {"brickgpt": 1 - set_share, "set": set_share}
        total = sum(shares[s] for s, _, _ in self.pools)
        self.pool_p = np.array([shares[s] / total for s, _, _ in self.pools])
        unknown = set(jitter) - set(shares)
        if unknown:
            raise ValueError(f"unknown jitter sources: {sorted(unknown)}")
        self.ranges: dict[int, tuple[int, int, int, int]] = {}  # build -> (z lo, z hi, x lo, x hi), jittered sources
        for source, members, _ in self.pools:
            if source in jitter:
                self.ranges.update(zip(members.tolist(), map(tuple, split.shift_ranges(members).tolist())))

    def sample(self, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        _, members, p = self.pools[rng.choice(len(self.pools), p=self.pool_p)]
        i = int(rng.choice(members, p=p))
        start = int(rng.integers(self.split.windows_of(i, self.count)))
        drop = bool(rng.random() < self.mask_drop)
        shift = (0, 0)
        if i in self.ranges:
            z_lo, z_hi, x_lo, x_hi = self.ranges[i]
            shift = (int(rng.integers(z_lo, z_hi + 1)), int(rng.integers(x_lo, x_hi + 1)))
        return self.split.window(i, start, self.count, drop, shift)

    def batch(self, size: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        return collate([self.sample(rng) for _ in range(size)], self.split.pad)


def set_builds(split: Split, sets: Sequence[str]) -> tuple[list[int], list[int]]:
    """(every build of the given real sets, in all their symmetries; only their untransformed builds) as
    indices into ``split``. Set builds are named ``<set>/sym<k>``; ``sym0`` is the set itself."""
    wanted = set(sets)
    found = {str(name).split("/")[0] for name in split.name}
    missing = wanted - found
    if missing:
        raise ValueError(f"sets not in this split: {sorted(missing)}")
    every = [i for i, name in enumerate(split.name) if str(name).split("/")[0] in wanted]
    return every, [i for i in every if str(split.name[i]).endswith("/sym0")]


def eval_windows(split: Split, max_len: int, limit: int | None = None,
                 indices: Sequence[int] | None = None) -> list[tuple[np.ndarray, np.ndarray]]:
    """Deterministic windows covering the first ``limit`` builds (all if None), or the builds ``indices``, at
    half-window stride, with their target masks."""
    count = max_parts(max_len)
    out = []
    chosen = indices if indices is not None else range(len(split) if limit is None else min(limit, len(split)))
    for i in chosen:
        n = split.size(i)
        starts = [0] if n <= count else list(range(0, n - count, count // 2)) + [n - count]
        out += [split.window(i, s, count, False) for s in starts]
    return out
