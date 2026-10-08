"""Learned proposal model on the CPU (M12b step 2): numpy inference of ``training/train.py``'s transformer.

``Proposal.load`` reads the exported weights (``proposal.npz``, float32 arrays in (in, out) layout plus the
config) and the ``tokens.Vocab`` saved next to them. The forward pass matches the PyTorch model exactly
(pre-LayerNorm blocks, causal attention, tanh-GELU MLP, learned positions, head tied to the token
embedding); ``tests/test_proposal.py`` checks it against logits saved from PyTorch.

``Proposal.session`` starts decoding one build: a key/value cache primed with the header and the target
mask (``tokens``). The bottom-up builder then asks, at each visited cell, for the model's weights of its
candidate (shape, color) choices (``Session.weights``) and reports every part it places (``Session.add``).
A query feeds the cell's ``Y Z X`` tokens, reads P(shape), feeds the most likely candidate shape, reads
P(color), and rolls the four tokens back; a placed part's five tokens are appended for good. When the cache
is full, it is rebuilt from the header (``CONT``), the mask and the last half-window of parts, as in
training (``training/data.py``).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.bricks.parts import PlacedPart, Shape
from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.tokens import (HEADER, MASK_PATCHES, MAX_XZ, MAX_Y, PART_TOKENS, PREFIX, Vocab, coarse_mask, header,
                                    mask_scale, part_tokens, patches)

LN_EPS = 1e-5
GELU_C = math.sqrt(2 / math.pi)


def layer_norm(x: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    mu = x.mean(axis=-1, keepdims=True)
    var = ((x - mu) ** 2).mean(axis=-1, keepdims=True)
    return (x - mu) / np.sqrt(var + LN_EPS) * g + b


def gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1 + np.tanh(GELU_C * (x + 0.044715 * x**3)))


def softmax(logits: np.ndarray) -> np.ndarray:
    z = np.exp(logits - logits.max(axis=-1, keepdims=True))
    return z / z.sum(axis=-1, keepdims=True)


@dataclass
class Cache:
    """Keys and values per layer, (heads, max_len, head dim), filled up to ``length``."""

    keys: list[np.ndarray]
    values: list[np.ndarray]
    length: int = 0


class Proposal:
    def __init__(self, weights: dict[str, np.ndarray], vocab: Vocab) -> None:
        self.w = {k: v.astype(np.float32) for k, v in weights.items() if k != "config"}
        config = json.loads(str(weights["config"]))
        self.d, self.layers, self.heads = config["d_model"], config["layers"], config["heads"]
        self.max_len = config["max_len"]
        if config["vocab"] != len(vocab) or config["prefix"] != PREFIX:
            raise ValueError("weights and vocabulary do not match")
        self.vocab = vocab
        self.head_dim = self.d // self.heads
        self.shape_tokens = vocab.shape_ids()
        self.color_tokens = vocab.color_ids()

    @classmethod
    def load(cls, path: Path, vocab_path: Path | None = None) -> "Proposal":
        path = Path(path)
        with np.load(path) as data:
            weights = {k: data[k] for k in data.files}
        return cls(weights, Vocab.load(vocab_path or path.with_name("vocab.json")))

    def choice_tokens(self, choices: Sequence[tuple[Shape, BrickColor]]) -> tuple[np.ndarray, np.ndarray]:
        """(shape ids, -1 where the vocabulary has no token; color ids, OTHER for unknown colors) of choices."""
        shapes = [self.vocab.shape(shape) for shape, _ in choices]
        return (np.array([-1 if t is None else t for t in shapes], dtype=np.int64),
                np.array([self.vocab.color(color) for _, color in choices], dtype=np.int64))

    # Forward pass ---------------------------------------------------------------------------------------

    def new_cache(self) -> Cache:
        shape = (self.heads, self.max_len, self.head_dim)
        return Cache([np.zeros(shape, np.float32) for _ in range(self.layers)],
                     [np.zeros(shape, np.float32) for _ in range(self.layers)])

    def embed_prefix(self, head: Sequence[int], mask_patches: np.ndarray) -> np.ndarray:
        """(PREFIX, d) input embeddings of the header tokens and the mask patches (positions not added)."""
        return np.concatenate([self.w["tok"][list(head)], mask_patches @ self.w["patch_w"] + self.w["patch_b"]])

    def run(self, cache: Cache, x: np.ndarray) -> np.ndarray:
        """Append input embeddings ``x`` (n, d) to the cache; logits (n, V) at those positions."""
        n, start = len(x), cache.length
        if start + n > self.max_len:
            raise ValueError(f"cache overflow: {start} + {n} > {self.max_len}")
        x = x + self.w["pos"][start : start + n]
        causal = np.triu(np.full((n, start + n), -np.inf, np.float32), k=start + 1)
        for i in range(self.layers):
            p = f"b{i}."
            qkv = layer_norm(x, self.w[p + "ln1_g"], self.w[p + "ln1_b"]) @ self.w[p + "qkv_w"] + self.w[p + "qkv_b"]
            q, k, v = (a.reshape(n, self.heads, self.head_dim).transpose(1, 0, 2) for a in np.split(qkv, 3, axis=-1))
            cache.keys[i][:, start : start + n] = k
            cache.values[i][:, start : start + n] = v
            keys, values = cache.keys[i][:, : start + n], cache.values[i][:, : start + n]
            scores = q @ keys.transpose(0, 2, 1) / math.sqrt(self.head_dim) + causal
            attn = (softmax(scores) @ values).transpose(1, 0, 2).reshape(n, self.d)
            x = x + attn @ self.w[p + "proj_w"] + self.w[p + "proj_b"]
            h = gelu(layer_norm(x, self.w[p + "ln2_g"], self.w[p + "ln2_b"]) @ self.w[p + "fc1_w"] + self.w[p + "fc1_b"])
            x = x + h @ self.w[p + "fc2_w"] + self.w[p + "fc2_b"]
        cache.length = start + n
        return layer_norm(x, self.w["ln_f_g"], self.w["ln_f_b"]) @ self.w["tok"].T

    def step(self, cache: Cache, ids: Sequence[int]) -> np.ndarray:
        """Append tokens; logits (n, V) after each."""
        return self.run(cache, self.w["tok"][list(ids)])

    def forward(self, ids: Sequence[int], mask_patches: np.ndarray) -> np.ndarray:
        """Logits for a whole sequence laid out as in training (``ids`` with any id in the mask slots)."""
        cache = self.new_cache()
        prefix = self.run(cache, self.embed_prefix(ids[:HEADER], mask_patches))
        return np.concatenate([prefix, self.step(cache, ids[PREFIX:])]) if len(ids) > PREFIX else prefix

    def session(self, grid_shape: tuple[int, int, int], allowed: np.ndarray | None = None, source: str = "set") -> "Session":
        """Start decoding a build in a (Y, Z, X) grid, with ``allowed`` as the target (None: no target)."""
        if allowed is None:
            head, mask = header(self.vocab, source, mask_scale(grid_shape), False), patches(None)
        else:
            scale, coarse = coarse_mask(allowed)
            head, mask = header(self.vocab, source, scale, True), patches(coarse)
        return Session(self, head, mask)


class Session:
    """One build being decoded: the parts so far and a cache over the current window."""

    def __init__(self, model: Proposal, head: list[int], mask_patches: np.ndarray) -> None:
        self.model, self.head, self.mask_patches = model, head, mask_patches
        self.rows: list[list[int]] = []  # tokens of every part placed so far
        self.window_parts = (model.max_len - PREFIX - 1) // PART_TOKENS
        self.queries = 0
        self._restart(0)

    def _restart(self, first: int) -> None:
        """Rebuild the cache from the header and the parts from index ``first`` on."""
        head = list(self.head)
        head[0] = self.model.vocab.id("BOS" if first == 0 else "CONT")
        self.cache = self.model.new_cache()
        self.logits = self.model.run(self.cache, self.model.embed_prefix(head, self.mask_patches))[-1]
        self.first = first
        if first < len(self.rows):
            self.logits = self.model.step(self.cache, [t for row in self.rows[first:] for t in row])[-1]

    def _make_room(self, tokens: int) -> None:
        if self.cache.length + tokens > self.model.max_len:
            self._restart(max(0, len(self.rows) - self.window_parts // 2))

    def add(self, part: PlacedPart) -> None:
        """Record a placed part (parts the vocabulary cannot express are left out of the context)."""
        try:
            row = part_tokens(part, self.model.vocab)
        except ValueError:
            return
        self._make_room(PART_TOKENS)
        self.rows.append(row)
        self.logits = self.model.step(self.cache, row)[-1]

    def weights(self, y: int, z: int, x: int, shape_ids: np.ndarray, color_ids: np.ndarray) -> np.ndarray:
        """Model weights of candidate choices (token ids from ``Proposal.choice_tokens``) for a part starting at
        cell (y, z, x): P(shape | parts so far, cell) x P(color | parts so far, cell, most likely candidate
        shape). Shapes the vocabulary lacks (id -1) get the uniform shape probability; outside the token grid
        every weight is 1."""
        if not (0 <= y < MAX_Y and 0 <= z < MAX_XZ and 0 <= x < MAX_XZ):
            return np.ones(len(shape_ids))
        vocab, model = self.model.vocab, self.model
        self._make_room(PART_TOKENS)
        self.queries += 1
        before = self.cache.length
        lookup = np.zeros(len(vocab))
        lookup[model.shape_tokens] = softmax(model.step(self.cache, [vocab.y(y), vocab.z(z), vocab.x(x)])[-1][model.shape_tokens])
        known = shape_ids >= 0
        shape_p = np.where(known, lookup[np.maximum(shape_ids, 0)], 1 / len(model.shape_tokens))
        color_p = np.ones(len(shape_ids))
        if known.any():
            top = int(shape_ids[known][np.argmax(shape_p[known])])
            lookup[:] = 0
            lookup[model.color_tokens] = softmax(model.step(self.cache, [top])[-1][model.color_tokens])
            color_p = lookup[color_ids]
        self.cache.length = before  # roll the query back
        return shape_p * color_p
