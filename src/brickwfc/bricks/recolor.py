"""Recolouring within part types (M12c): the colours of a build's parts permuted among the parts of each part type to
make its skin more colour-coherent (``bricks.coherence``).

The search space is exactly ``coherence.shuffled``'s: every placement stays and every (part, colour) count stays,
so validity, support, physics, one piece, completeness and the inventory are unchanged by construction. A part
with no skin face (inside the build) shows nothing, so it is a free reservoir: swapping its colour with a visible
part of its type moves an off-colour out of sight.

Score (higher is better), over the skin's visible part pairs P and full 4 x 4 skin windows W as in ``coherence``:

    score = same-colour share of P  -  WINDOW_WEIGHT x mean distinct colours per window of W

``WINDOW_WEIGHT`` = 0.25: one colour less per window on average is worth 25 points of same-colour seams (the gap to
the real sets measured in results/m12c_colour_measure.md is about 22 points and 0.73 colours per window, so the two
terms weigh about equally there).

Search: simulated annealing with a fixed budget of ``PROPOSALS_PER_PART`` proposals per movable visible part (a part
on the skin whose type comes in more than one colour in the build). A proposal picks such a part and a part of its
type with another colour (visible or not) and swaps their colours if the score rises, or, if it falls, with
probability exp(gain / T); T falls linearly from ``START_TEMPERATURE`` (in units of one seam's share, 1 / |P|) to 0,
so the search ends greedy; the best colouring seen is returned. Each proposal is scored incrementally from the
pairs and windows the two parts are in.
Deterministic given the Generator. With temperature 0 it is first-improvement hill climbing, which stops in a local
optimum early (on the complete chair: the same result at 100 to 1000 proposals per part, 2-3 seam points under
annealing's).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from brickwfc.bricks.coherence import Coherence, coherence, visible_pairs
from brickwfc.bricks.parts import PlacedPart
from brickwfc.bricks.skin import DOWN_STEP, PATCH, SIDE_STEPS, UP_STEP, exposed, exterior, owners

WINDOW_WEIGHT = 0.25
PROPOSALS_PER_PART = 1000
START_TEMPERATURE = 1.0


@dataclass(frozen=True)
class Recoloring:
    placed: list[PlacedPart]  # the build, recoloured
    before: Coherence
    after: Coherence
    proposals: int
    swaps: int  # accepted
    visible_parts: int  # parts with a skin face
    movable_parts: int  # of which their type comes in more than one colour
    fixed_skin_share: float  # share of skin cells on parts whose type comes in one colour only (cannot change)
    seconds: float


def skin_structure(placed: Sequence[PlacedPart], shape: tuple[int, int, int], patch: int = PATCH):
    """(visible pairs, windows as tuples of the distinct parts each shows, the skin cells' owners)."""
    owner = owners(placed, shape)
    filled = owner >= 0
    outside = exterior(filled)
    pairs: set[tuple[int, int]] = set()
    windows: list[tuple[int, ...]] = []
    on_skin = np.zeros(shape, dtype=bool)
    for step in (UP_STEP, DOWN_STEP, *SIDE_STEPS):
        mask = exposed(filled, outside, step)
        on_skin |= mask
        axis = int(np.flatnonzero(step)[0])
        faces = np.where(mask, owner, -1)
        pairs |= visible_pairs(faces, axis)
        if step == DOWN_STEP:
            continue
        planes = np.moveaxis(faces, axis, 0)
        if planes.shape[1] < patch or planes.shape[2] < patch:
            continue
        found = sliding_window_view(planes, (patch, patch), axis=(1, 2)).reshape(-1, patch * patch)
        for row in found[(found >= 0).all(axis=1)]:
            windows.append(tuple(np.unique(row).tolist()))
    return sorted(pairs), windows, owner[on_skin]


def score(colors: Sequence[int], pairs: Sequence[tuple[int, int]], windows: Sequence[tuple[int, ...]]) -> float:
    same = sum(colors[i] == colors[j] for i, j in pairs) / len(pairs) if pairs else 0.0
    distinct = sum(len({colors[i] for i in w}) for w in windows) / len(windows) if windows else 0.0
    return same - WINDOW_WEIGHT * distinct


def recolor(placed: Sequence[PlacedPart], shape: tuple[int, int, int], rng: np.random.Generator,
            proposals_per_part: int = PROPOSALS_PER_PART, start_temperature: float = START_TEMPERATURE) -> Recoloring:
    """``placed`` recoloured within part types to raise ``score`` (see the module docstring)."""
    clock = time.perf_counter()
    pairs, windows, skin_owner = skin_structure(placed, shape)
    names = sorted({p.color.name for p in placed})
    palette = {name: next(p.color for p in placed if p.color.name == name) for name in names}
    colors = [names.index(p.color.name) for p in placed]
    neighbors: list[list[int]] = [[] for _ in placed]
    for i, j in pairs:
        neighbors[i].append(j)
        neighbors[j].append(i)
    in_windows: list[list[int]] = [[] for _ in placed]
    tally: list[dict[int, int]] = []  # per window: colour -> parts of that colour in it
    for w, parts in enumerate(windows):
        counts: dict[int, int] = {}
        for i in parts:
            in_windows[i].append(w)
            counts[colors[i]] = counts.get(colors[i], 0) + 1
        tally.append(counts)
    by_type: dict[str, list[int]] = {}
    for i, part in enumerate(placed):
        by_type.setdefault(part.shape.part.name, []).append(i)
    visible = sorted(set(skin_owner.tolist()))
    movable = [i for i in visible if len({colors[k] for k in by_type[placed[i].shape.part.name]}) > 1]
    fixed = np.isin(skin_owner, [i for i in visible if i not in set(movable)]).mean() if len(skin_owner) else 0.0
    n_pairs, n_windows = max(len(pairs), 1), max(len(windows), 1)

    def window_delta(a: int, b: int, ca: int, cb: int) -> int:
        """Change in summed distinct colours if part ``a`` turns from ``ca`` to ``cb`` (windows without ``b``)."""
        delta = 0
        for w in in_windows[a]:
            if b in windows[w]:
                continue
            t = tally[w]
            delta += (t.get(cb, 0) == 0) - (t[ca] == 1)
        return delta

    def pair_delta(a: int, b: int, ca: int, cb: int) -> int:
        return sum((cb == colors[j]) - (ca == colors[j]) for j in neighbors[a] if j != b)

    def move(a: int, ca: int, cb: int, skip: int) -> None:
        for w in in_windows[a]:
            if skip in windows[w]:
                continue
            t = tally[w]
            t[ca] -= 1
            if not t[ca]:
                del t[ca]
            t[cb] = t.get(cb, 0) + 1

    budget = proposals_per_part * len(movable)
    swaps = 0
    current = best = 0.0  # the score relative to the start
    best_colors = list(colors)
    for step in range(budget):
        temperature = start_temperature * (1 - step / budget) / n_pairs
        a = movable[int(rng.integers(len(movable)))]
        ca = colors[a]
        others = [k for k in by_type[placed[a].shape.part.name] if colors[k] != ca]
        b = others[int(rng.integers(len(others)))]
        cb = colors[b]
        gain = ((pair_delta(a, b, ca, cb) + pair_delta(b, a, cb, ca)) / n_pairs
                - WINDOW_WEIGHT * (window_delta(a, b, ca, cb) + window_delta(b, a, cb, ca)) / n_windows)
        if gain > 1e-12 or (temperature > 0 and rng.random() < np.exp(gain / temperature)):
            move(a, ca, cb, b)
            move(b, cb, ca, a)
            colors[a], colors[b] = cb, ca
            swaps += 1
            current += gain
            if current > best + 1e-12:
                best, best_colors = current, list(colors)
    out = [PlacedPart(p.shape, palette[names[c]], p.layer, p.x, p.z) for p, c in zip(placed, best_colors)]
    return Recoloring(out, coherence(placed, shape), coherence(out, shape), budget, swaps, len(visible), len(movable),
                      float(fixed), time.perf_counter() - clock)
