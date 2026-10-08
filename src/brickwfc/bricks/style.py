"""Learned style (M10): how parts sit on and beside each other in real sets, and a judge.

A build is described by its **contacts**:

- *vertical*: part U rests on part L (some cell of U's bottom layer is directly above L's top);
- *horizontal*: parts A and B touch side by side (neighboring cells on the same layer);
- *support count*: how many parts each part above the ground rests on (1, 2, or 3+; 2+ means it
  bridges parts, as in a running bond).

``StyleStats`` counts, over a set of models: which part type sits on which (P(U | L)), which sits
beside which (P(B | A)), how often touching parts share a color, the support counts, and the part
and color frequencies. Part types are ``parts.CATALOG`` names; colors enter only as same/different,
so the statistics carry over to sets with other palettes.

``distance`` compares two builds' (or collections') statistics with Jensen-Shannon divergences.
``judge`` scores a build by how far its own contact statistics are from the learned ones
(``total`` = -divergence, higher = more like the training sets). It also reports the mean
log-likelihood per contact, but that alone is not a usable judge: it is maximised by repeating
the single most common contact (a tower of identical bricks beats every real model), while the
divergence ranks such builds below real ones.
``StyleBias`` turns learned statistics into sampling weights for the generators: a candidate part is
weighted by how much more likely it is next to its neighbors than on average (a likelihood ratio).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from brickwfc.bricks.colors import BrickColor
from brickwfc.bricks.parts import CATALOG, PartSet, PlacedPart, part_tileset, shapes_of

TYPES: list[str] = list(CATALOG)
TYPE_INDEX: dict[str, int] = {name: i for i, name in enumerate(TYPES)}
SUPPORT_BINS = 3  # rests on 1, 2, 3+ parts
ALPHA = 0.5  # additive smoothing for part-type distributions


@dataclass(frozen=True)
class Contacts:
    vertical: list[tuple[int, int]]  # (lower, upper) indices into the placed list
    horizontal: list[tuple[int, int]]  # (a, b) with a < b
    supports: list[int]  # for each part above the ground: number of distinct parts below it


def occupancy(placed: Sequence[PlacedPart]) -> np.ndarray:
    """(Y, Z, X) part indices, -1 where empty; the grid is just big enough for the parts."""
    if not placed:
        return np.full((1, 1, 1), -1, dtype=np.int64)
    cells = [cell for part in placed for cell in part.cells()]
    shape = tuple(max(c[i] for c in cells) + 1 for i in range(3))
    owner = np.full(shape, -1, dtype=np.int64)
    for i, part in enumerate(placed):
        for cell in part.cells():
            owner[cell] = i
    return owner


def contacts(placed: Sequence[PlacedPart]) -> Contacts:
    owner = occupancy(placed)
    vertical: set[tuple[int, int]] = set()
    supports: list[int] = []
    for i, part in enumerate(placed):
        if part.layer == 0:
            continue
        below = {int(owner[y - 1, z, x]) for y, z, x in part.bottom_cells()} - {-1, i}
        vertical.update((j, i) for j in below)
        supports.append(len(below))
    horizontal: set[tuple[int, int]] = set()
    for axis in (1, 2):
        a = np.moveaxis(owner, axis, 0)[:-1].ravel()
        b = np.moveaxis(owner, axis, 0)[1:].ravel()
        touching = (a >= 0) & (b >= 0) & (a != b)
        horizontal.update(zip(np.minimum(a, b)[touching].tolist(), np.maximum(a, b)[touching].tolist()))
    return Contacts(sorted(vertical), sorted(horizontal), supports)


def _type(part: PlacedPart) -> int:
    return TYPE_INDEX[part.shape.part.name]


@dataclass
class StyleStats:
    """Counts over one or more models (add more with ``add``)."""

    parts: np.ndarray = field(default_factory=lambda: np.zeros(len(TYPES)))
    colors: dict[str, float] = field(default_factory=dict)
    vertical: np.ndarray = field(default_factory=lambda: np.zeros((len(TYPES), len(TYPES))))  # [lower, upper]
    horizontal: np.ndarray = field(default_factory=lambda: np.zeros((len(TYPES), len(TYPES))))  # symmetric
    same_color: np.ndarray = field(default_factory=lambda: np.zeros((2, 2)))  # [vertical/horizontal, same/total]
    supports: np.ndarray = field(default_factory=lambda: np.zeros(SUPPORT_BINS))
    models: int = 0

    def add(self, placed: Sequence[PlacedPart]) -> "StyleStats":
        for part in placed:
            self.parts[_type(part)] += 1
            self.colors[part.color.name] = self.colors.get(part.color.name, 0.0) + 1
        self.add_events(events(placed))
        self.models += 1
        return self

    def add_events(self, found: "Events") -> "StyleStats":
        """Add contact events only (no part or color counts, no model count)."""
        np.add.at(self.vertical, (found.vertical[:, 0], found.vertical[:, 1]), 1)
        np.add.at(self.horizontal, (found.horizontal[:, 0], found.horizontal[:, 1]), 1)
        np.add.at(self.horizontal, (found.horizontal[:, 1], found.horizontal[:, 0]), 1)
        for row, pairs in ((0, found.vertical), (1, found.horizontal)):
            self.same_color[row] += (pairs[:, 2].sum(), len(pairs))
        np.add.at(self.supports, found.supports, 1)
        return self

    def __add__(self, other: "StyleStats") -> "StyleStats":
        colors = dict(self.colors)
        for name, count in other.colors.items():
            colors[name] = colors.get(name, 0.0) + count
        return StyleStats(self.parts + other.parts, colors, self.vertical + other.vertical,
                          self.horizontal + other.horizontal, self.same_color + other.same_color,
                          self.supports + other.supports, self.models + other.models)

    def scaled(self, factor: float) -> "StyleStats":
        """Every count times ``factor`` (the model count rounded)."""
        return StyleStats(self.parts * factor, {name: count * factor for name, count in self.colors.items()},
                          self.vertical * factor, self.horizontal * factor, self.same_color * factor,
                          self.supports * factor, round(self.models * factor))

    # Smoothed probabilities -------------------------------------------------------------------

    def p_part(self) -> np.ndarray:
        return (self.parts + ALPHA) / (self.parts.sum() + ALPHA * len(TYPES))

    def p_upper(self) -> np.ndarray:
        """P(U | L), rows indexed by the lower part type."""
        return (self.vertical + ALPHA) / (self.vertical.sum(axis=1, keepdims=True) + ALPHA * len(TYPES))

    def p_beside(self) -> np.ndarray:
        """P(B | A) for side-by-side contacts."""
        return (self.horizontal + ALPHA) / (self.horizontal.sum(axis=1, keepdims=True) + ALPHA * len(TYPES))

    def p_same_color(self) -> np.ndarray:
        """(vertical, horizontal) probability that touching parts share a color."""
        return (self.same_color[:, 0] + 1) / (self.same_color[:, 1] + 2)

    def p_supports(self) -> np.ndarray:
        return (self.supports + 1) / (self.supports.sum() + SUPPORT_BINS)

    # Persistence ---------------------------------------------------------------------------

    def to_json(self) -> dict:
        nonzero = lambda m: [[TYPES[i], TYPES[j], float(m[i, j])] for i, j in zip(*np.nonzero(m))]  # noqa: E731
        return {
            "types": TYPES, "models": self.models, "parts": dict(zip(TYPES, self.parts.tolist())), "colors": self.colors,
            "vertical": nonzero(self.vertical), "horizontal": nonzero(self.horizontal),
            "same_color": self.same_color.tolist(), "supports": self.supports.tolist(),
        }

    @classmethod
    def from_json(cls, data: dict) -> "StyleStats":
        stats = cls(models=data["models"], colors=dict(data["colors"]))
        for name, count in data["parts"].items():
            stats.parts[TYPE_INDEX[name]] = count
        for key in ("vertical", "horizontal"):
            matrix = getattr(stats, key)
            for a, b, count in data[key]:
                matrix[TYPE_INDEX[a], TYPE_INDEX[b]] = count
        stats.same_color = np.array(data["same_color"], dtype=float)
        stats.supports = np.array(data["supports"], dtype=float)
        return stats

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json()), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "StyleStats":
        return cls.from_json(json.loads(path.read_text(encoding="utf-8")))


def learn(models: Sequence[Sequence[PlacedPart]]) -> StyleStats:
    stats = StyleStats()
    for placed in models:
        stats.add(placed)
    return stats


def merged(parts: Sequence[StyleStats]) -> StyleStats:
    """Statistics of several models learned separately (``learn`` of all of them at once, but cheaper
    when the same models are combined many ways, as in cross-validation)."""
    total = StyleStats()
    for stats in parts:
        total = total + stats
    return total


# Contact events and size-matched references ------------------------------------------------------


@dataclass(frozen=True)
class Events:
    """A build's contact events as arrays: (lower type, upper type, same color) per vertical contact,
    (type a, type b, same color) per side-by-side contact, support-count bin per part above ground."""

    vertical: np.ndarray  # (n, 3) int
    horizontal: np.ndarray  # (n, 3) int
    supports: np.ndarray  # (n,) int in [0, SUPPORT_BINS)

    @property
    def count(self) -> int:
        """Number of judge terms: a type and a color term per contact, a term per support count."""
        return 2 * len(self.vertical) + 2 * len(self.horizontal) + len(self.supports)


def events(placed: Sequence[PlacedPart]) -> Events:
    found = contacts(placed)

    def rows(pairs: list[tuple[int, int]]) -> np.ndarray:
        data = [(_type(placed[i]), _type(placed[j]), int(placed[i].color == placed[j].color)) for i, j in pairs]
        return np.array(data, dtype=np.int64).reshape(-1, 3)

    supports = np.array([min(n, SUPPORT_BINS) - 1 for n in found.supports], dtype=np.int64)
    return Events(rows(found.vertical), rows(found.horizontal), supports)


def subsample(found: Events, count: int, rng: np.random.Generator) -> Events:
    """About ``count`` judge terms drawn without replacement, keeping the mix of vertical, side and
    support events. Returns all events if ``count`` is not smaller."""
    if count >= found.count or found.count == 0:
        return found
    fraction = count / found.count

    def draw(array: np.ndarray) -> np.ndarray:
        k = int(round(fraction * len(array)))
        return array[np.sort(rng.choice(len(array), size=k, replace=False))] if k else array[:0]

    return Events(draw(found.vertical), draw(found.horizontal), draw(found.supports))


def matched_divergence(reference: Events, count: int, stats: StyleStats, rng: np.random.Generator, draws: int = 5) -> float:
    """Mean divergence from ``stats`` of ``draws`` subsamples of ``reference`` with ``count`` judge terms
    (all of ``reference`` if it is not larger): what it scores at that size."""
    if count >= reference.count:
        return distance(StyleStats().add_events(reference), stats)["mean"]
    values = [distance(StyleStats().add_events(subsample(reference, count, rng)), stats)["mean"] for _ in range(draws)]
    return float(np.mean(values))


def size_matched(build: Events, real: Events, stats: StyleStats, rng: np.random.Generator,
                 draws: int = 5) -> tuple[float, float, int]:
    """Judge a build and a real model at the same size: both are subsampled to the smaller one's number
    of judge terms. Returns (build's judge, real model's judge, that size); judge = -divergence."""
    count = min(build.count, real.count)
    return -matched_divergence(build, count, stats, rng, draws), -matched_divergence(real, count, stats, rng, draws), count


# Judge -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Score:
    total: float  # -divergence: higher = more like the training sets (0 = identical statistics)
    divergence: float  # ``distance(build, learned)['mean']``, in [0, 1]
    likelihood: float  # mean log-likelihood per event (all terms below); reported, not the judge
    vertical: float  # mean log P(U | L)
    horizontal: float  # mean log P(B | A)
    color: float  # mean log P(same / different color) over all contacts
    support: float  # mean log P(support count)
    events: int


def judge(placed: Sequence[PlacedPart], stats: StyleStats) -> Score:
    found = contacts(placed)
    p_up, p_side, p_same, p_sup = stats.p_upper(), stats.p_beside(), stats.p_same_color(), stats.p_supports()
    vertical = [math.log(p_up[_type(placed[i]), _type(placed[j])]) for i, j in found.vertical]
    horizontal = [math.log(p_side[_type(placed[i]), _type(placed[j])]) for i, j in found.horizontal]
    color = [
        math.log(p_same[row] if placed[i].color == placed[j].color else 1 - p_same[row])
        for row, pairs in ((0, found.vertical), (1, found.horizontal))
        for i, j in pairs
    ]
    support = [math.log(p_sup[min(n, SUPPORT_BINS) - 1]) for n in found.supports]
    terms = vertical + horizontal + color + support

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    divergence = distance(StyleStats().add(placed), stats)["mean"]
    return Score(-divergence, divergence, mean(terms), mean(vertical), mean(horizontal), mean(color), mean(support),
                 len(terms))


# Distance between two builds' own statistics ---------------------------------------------------


def js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence (base 2, in [0, 1]) between two count arrays; 0 if both empty."""
    p, q = np.asarray(p, dtype=float).ravel(), np.asarray(q, dtype=float).ravel()
    if p.sum() == 0 or q.sum() == 0:
        return 0.0 if p.sum() == q.sum() else 1.0
    p, q = p / p.sum(), q / q.sum()
    m = (p + q) / 2

    def kl(a: np.ndarray) -> float:
        mask = a > 0
        return float((a[mask] * np.log2(a[mask] / m[mask])).sum())

    return (kl(p) + kl(q)) / 2


def distance(a: StyleStats, b: StyleStats) -> dict[str, float]:
    """How far apart two builds' statistics are: JS divergence of their vertical, horizontal and
    support-count distributions, and the gap in their same-color rates; ``mean`` averages the JS terms
    and the two color gaps."""
    rate = lambda s: s.same_color[:, 0] / np.maximum(s.same_color[:, 1], 1)  # noqa: E731
    gaps = np.abs(rate(a) - rate(b))
    result = {
        "vertical_js": js_divergence(a.vertical, b.vertical),
        "horizontal_js": js_divergence(np.triu(a.horizontal), np.triu(b.horizontal)),
        "support_js": js_divergence(a.supports, b.supports),
        "color_gap_vertical": float(gaps[0]),
        "color_gap_horizontal": float(gaps[1]),
    }
    result["mean"] = float(np.mean(list(result.values())))
    return result



def styled_tileset(inventory: dict[tuple[str, str], int], colors: Sequence[BrickColor], empty_weight_per_part: float,
                   stats: StyleStats | None = None) -> PartSet:
    """A tileset over the inventory's (part, color) pairs. Each pair is equally likely per part placed,
    or, with ``stats``, as likely as the learned part-type frequency times the learned color frequency
    (both smoothed and restricted to the inventory's parts and colors). The empty tile weighs
    ``empty_weight_per_part`` per part type."""
    names = sorted({name for name, _ in inventory})
    coverage = {}
    for name, color in inventory:
        part = CATALOG[name]
        share = 1.0
        if stats is not None:
            share = (stats.parts[TYPE_INDEX[name]] + ALPHA) * (stats.colors.get(color, 0.0) + 1)
        for shape in shapes_of([part]):
            orientations = 2 if part.width != part.depth else 1
            coverage[(shape.name, color)] = share * shape.cells / orientations
    return part_tileset([CATALOG[n] for n in names], colors, len(names) * empty_weight_per_part, coverage=coverage)

# Sampling bias for the generators --------------------------------------------------------------


class StyleBias:
    """Likelihood-ratio weights from learned statistics.

    For a candidate part of type B and color c next to an existing part A (color a):
    vertical (B on A): ``P(B | A) / P(B)`` times ``P(same) / q`` if c == a else ``(1 - P(same)) / (1 - q)``,
    where P(B) is B's share among upper parts and q is the chance two parts share a color under the
    generator's own color weights; horizontal contacts likewise. Factors multiply over contacts and are
    raised to ``strength`` (0 turns the bias off).
    """

    def __init__(self, stats: StyleStats, parts: PartSet, strength: float = 1.0) -> None:
        self.strength = strength
        p_up, p_side = stats.p_upper(), stats.p_beside()
        upper_marginal = (stats.vertical.sum(axis=0) + ALPHA) / (stats.vertical.sum() + ALPHA * len(TYPES))
        side_marginal = (stats.horizontal.sum(axis=0) + ALPHA) / (stats.horizontal.sum() + ALPHA * len(TYPES))
        self.lift = np.stack([p_up / upper_marginal[None, :], p_side / side_marginal[None, :]])  # [kind, A, B]
        # Chance that two parts share a color under the generator's weights (solid tiles' color shares).
        shares: dict[str, float] = {}
        for info, weight in zip(parts.infos, parts.tileset.weights):
            if info.solid:
                shares[info.color.name] = shares.get(info.color.name, 0.0) + float(weight)
        total = sum(shares.values())
        q = sum((w / total) ** 2 for w in shares.values()) if total else 0.0
        q = min(max(q, 1e-6), 1 - 1e-6)
        same = stats.p_same_color()
        self.color_factor = np.array([[(1 - same[k]) / (1 - q), same[k] / q] for k in range(2)])  # [kind, same?]
        # Per tile: part type (-1 empty), color id, layer flags, and whether its part continues toward
        # each horizontal neighbor (then that neighbor is the same part, not a contact).
        self.color_ids: dict[str, int] = {}
        self.tile_type = np.array([TYPE_INDEX[i.shape.part.name] if i.solid else -1 for i in parts.infos])
        self.tile_color = np.array([self.color_id(i.color.name) if i.solid else -1 for i in parts.infos])
        self.tile_bottom = parts.bottom
        self.tile_stud_top = parts.stud_top
        self.sides = ((0, -1), (0, 1), (-1, 0), (1, 0))  # (dz, dx)
        self.continues = {side: np.array([i.inside(side[1], side[0]) for i in parts.infos]) for side in self.sides}

    def color_id(self, name: str) -> int:
        return self.color_ids.setdefault(name, len(self.color_ids))

    def factors(self, kind: int, neighbor_type: int, neighbor_color: int, types: np.ndarray, colors: np.ndarray) -> np.ndarray:
        """Weights for candidates (``types``, color ids ``colors``) touching one part; ``kind`` 0 = on top of
        it, 1 = beside it."""
        return self.lift[kind, neighbor_type, types] * self.color_factor[kind, (colors == neighbor_color).astype(int)]

    def for_choices(self, context: Sequence[tuple[int, PlacedPart]], types: np.ndarray, colors: np.ndarray) -> np.ndarray:
        """Bottom-up builder: weights for candidate (type, color id) choices given the parts they would
        touch (``context`` = [(kind, part)], kind 0 = the part below, 1 = a part beside)."""
        weight = np.ones(len(types))
        for kind, part in context:
            weight *= self.factors(kind, _type(part), self.color_id(part.color.name), types, colors)
        return weight ** self.strength

    def for_tiles(self, domain: np.ndarray, cell: tuple[int, int, int]) -> np.ndarray:
        """WFC: weights over all tiles for ``cell`` given its already-fixed neighbors. A tile that starts a
        part on a fixed stud top below, or that sits beside a fixed tile of another part, is weighted
        against that part; tiles continuing a part, and empty, get 1."""
        y, z, x = cell
        _, nz, nx, _ = domain.shape
        weight = np.ones(domain.shape[-1])
        solid = self.tile_type >= 0
        if y > 0 and domain[y - 1, z, x].sum() == 1:
            below = int(domain[y - 1, z, x].argmax())
            if self.tile_stud_top[below]:
                mask = solid & self.tile_bottom
                weight[mask] *= self.factors(0, self.tile_type[below], self.tile_color[below], self.tile_type[mask],
                                             self.tile_color[mask])
        for dz, dx in self.sides:
            zz, xx = z + dz, x + dx
            if not (0 <= zz < nz and 0 <= xx < nx) or domain[y, zz, xx].sum() != 1:
                continue
            neighbor = int(domain[y, zz, xx].argmax())
            if self.tile_type[neighbor] < 0:
                continue
            mask = solid & ~self.continues[(dz, dx)]
            weight[mask] *= self.factors(1, self.tile_type[neighbor], self.tile_color[neighbor], self.tile_type[mask],
                                         self.tile_color[mask])
        return weight ** self.strength
