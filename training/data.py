"""Training windows from the exported token data (``experiments/export_tokens.py``). numpy only, so it is
tested without PyTorch and shared by ``train.py``.

A window is one model input: the 4 header tokens, the 64 mask patches, and up to ``max_parts`` consecutive
parts of one build (5 tokens each), then EOS if the window reaches the build's end. A window that does not
start at the build's first part has ``CONT`` instead of ``BOS``. With probability ``mask_drop`` the target
is dropped (``NOMASK``, zero patches), so the model also proposes without a target.

Layout of ``ids`` (length ``PREFIX + 5 * parts (+ 1)``): header ids, then ``PAD`` in the 64 mask slots (the
model puts the patch embeddings there), then the part tokens. The loss is on every position from ``PREFIX``
on (the first part's Y is predicted from the last mask slot).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HEADER, MASK_PATCHES, PATCH, MASK_GRID, PART_TOKENS = 4, 64, 5, 20, 5
PREFIX = HEADER + MASK_PATCHES
PATCH_BITS = PATCH**3


def max_parts(max_len: int) -> int:
    """Parts per window so that the window and its EOS fit in ``max_len`` positions."""
    return (max_len - PREFIX - 1) // PART_TOKENS


def patches(packed: np.ndarray) -> np.ndarray:
    """(64, 125) float32 patch vectors from a packed 20^3 mask (``bricks.tokens.patches`` layout)."""
    mask = np.unpackbits(packed)[: MASK_GRID**3].reshape(MASK_GRID, MASK_GRID, MASK_GRID)
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

    def __len__(self) -> int:
        return len(self.header)

    def size(self, i: int) -> int:
        """Parts in build ``i``."""
        return int(self.offsets[i + 1] - self.offsets[i])

    def window(self, i: int, start: int, count: int, drop_mask: bool) -> tuple[np.ndarray, np.ndarray]:
        """(ids, patches) of build ``i`` from part ``start``, at most ``count`` parts."""
        n = self.size(i)
        end = min(n, start + count)
        head = self.header[i].copy()
        head[0] = self.bos if start == 0 else self.cont
        if drop_mask:
            head[3] = self.nomask
        rows = self.parts[self.offsets[i] + start : self.offsets[i] + end].ravel()
        tail = [self.eos] if end == n else []
        ids = np.concatenate([head, np.full(MASK_PATCHES, self.pad), rows, tail]).astype(np.int64)
        mask = np.zeros((MASK_PATCHES, PATCH_BITS), np.float32) if drop_mask else patches(self.masks[i])
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
    of that source with probability proportional to its number of windows, then a start uniformly."""

    def __init__(self, split: Split, max_len: int, set_share: float, mask_drop: float) -> None:
        self.split, self.count, self.mask_drop = split, max_parts(max_len), mask_drop
        weights = np.array([min(split.size(i), 10 * self.count) / self.count + 1 for i in range(len(split))])
        self.pools = []
        for source in ("brickgpt", "set"):
            members = np.flatnonzero(split.source == source)
            if len(members):
                self.pools.append((source, members, weights[members] / weights[members].sum()))
        shares = {"brickgpt": 1 - set_share, "set": set_share}
        total = sum(shares[s] for s, _, _ in self.pools)
        self.pool_p = np.array([shares[s] / total for s, _, _ in self.pools])

    def sample(self, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        _, members, p = self.pools[rng.choice(len(self.pools), p=self.pool_p)]
        i = int(rng.choice(members, p=p))
        start = int(rng.integers(self.split.windows_of(i, self.count)))
        return self.split.window(i, start, self.count, bool(rng.random() < self.mask_drop))

    def batch(self, size: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        return collate([self.sample(rng) for _ in range(size)], self.split.pad)


def eval_windows(split: Split, max_len: int, limit: int | None = None) -> list[tuple[np.ndarray, np.ndarray]]:
    """Deterministic windows covering the first ``limit`` builds (all if None) at half-window stride, with
    their target masks."""
    count = max_parts(max_len)
    out = []
    for i in range(len(split) if limit is None else min(limit, len(split))):
        n = split.size(i)
        starts = [0] if n <= count else list(range(0, n - count, count // 2)) + [n - count]
        out += [split.window(i, s, count, False) for s in starts]
    return out
