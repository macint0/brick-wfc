"""M12b step 2d: the bottom-up builder with a learned proposal and a raster visit order."""

import hashlib
from collections import Counter

import numpy as np
import pytest

from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.inventory import overuse
from brickwfc.bricks.parts import CATALOG, extract_parts, part_tileset
from brickwfc.bricks.proposal import Proposal, random_weights
from brickwfc.bricks.style import StyleBias, StyleStats
from brickwfc.bricks.support import is_stable
from brickwfc.bricks.tokens import build_vocab
from conftest import tiny_model

RED, BLUE = colors_by_name(["red", "blue"])
PARTS = [CATALOG[n] for n in ("plate1x1", "plate1x2", "plate2x4", "brick1x2", "brick2x2", "tile1x2")]


class FixedProposal:
    """A stand-in model: every query weights the choices by a fixed preference; records placed parts."""

    def __init__(self, favorite: str) -> None:
        self.favorite = favorite
        self.sessions: list["FixedSession"] = []

    def choice_tokens(self, choices):
        favored = np.array([shape.part.name == self.favorite for shape, _ in choices], dtype=np.int64)
        return favored, np.zeros(len(choices), dtype=np.int64)

    def session(self, grid_shape, allowed=None):
        self.sessions.append(FixedSession())
        return self.sessions[-1]


class FixedSession:
    def __init__(self) -> None:
        self.added = []
        self.queries = 0

    def weights(self, y, z, x, favored, _colors):
        self.queries += 1
        return np.where(favored == 1, 1.0, 1e-3)

    def add(self, part) -> None:
        self.added.append(part)


def check(grid: np.ndarray, parts, inventory=None) -> list:
    placed, errors = extract_parts(grid, parts)
    assert not errors and is_stable(placed, parts.solid[grid])
    if inventory is not None:
        assert not overuse(placed, inventory)
    return placed


def test_order_option() -> None:
    parts = part_tileset(PARTS, [RED, BLUE])
    with pytest.raises(ValueError):
        BottomUpBuilder(parts, order="spiral")
    default, explicit = BottomUpBuilder(parts, any_offset=True), BottomUpBuilder(parts, any_offset=True, order="random")
    for seed in range(3):
        assert np.array_equal(default.build((6, 5, 5), np.random.default_rng(seed)),
                              explicit.build((6, 5, 5), np.random.default_rng(seed)))
        check(BottomUpBuilder(parts, any_offset=True, order="raster").build((6, 5, 5), np.random.default_rng(seed)), parts)


def test_proposal_steers_choices_and_sees_every_part() -> None:
    parts = part_tileset(PARTS, [RED, BLUE])
    proposal = FixedProposal("plate2x4")
    steered = BottomUpBuilder(parts, any_offset=True, order="raster", proposal=proposal, proposal_strength=2.0)
    plain = BottomUpBuilder(parts, any_offset=True, order="raster")
    counts = {"steered": Counter(), "plain": Counter()}
    for seed in range(5):
        for name, builder in (("steered", steered), ("plain", plain)):
            placed = check(builder.build((6, 8, 8), np.random.default_rng(seed)), parts)
            counts[name].update(p.shape.part.name for p in placed)
        assert proposal.sessions[-1].added == placed_order(proposal.sessions[-1].added)
    share = {k: c["plate2x4"] / sum(c.values()) for k, c in counts.items()}
    assert share["steered"] > 2 * share["plain"]
    assert all(s.queries > 0 for s in proposal.sessions)


def placed_order(parts: list) -> list:
    """Parts sorted by layer (the builder places layer by layer)."""
    return sorted(parts, key=lambda p: p.layer)


def test_masks_hold_with_a_real_model_and_builds_are_seeded() -> None:
    parts = part_tileset(PARTS, [RED, BLUE])
    vocab = build_vocab()
    model = Proposal(random_weights(vocab, np.random.default_rng(0), max_len=256), vocab)
    inventory = {("plate2x4", "red"): 3, ("brick2x2", "blue"): 4, ("plate1x2", "red"): 6, ("tile1x2", "blue"): 2}
    allowed = np.zeros((6, 6, 6), dtype=bool)
    allowed[:, 1:5, 1:5] = True
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True, connect=True, connect_rounds=3, order="raster",
                              proposal=model)
    for seed in range(3):
        grid = builder.build((6, 6, 6), np.random.default_rng(seed), inventory, allowed)
        placed = check(grid, parts, inventory)
        assert placed and all(allowed[c] for p in placed for c in p.cells())
        assert np.array_equal(grid, builder.build((6, 6, 6), np.random.default_rng(seed), inventory, allowed))


# Default builds are byte-identical to main before the hook (fingerprints recorded at e2a0e91).
DEFAULT_FINGERPRINTS = {
    "d2": ["5cc3994f83deea36", "8dc680590f3fbddd", "8c3b96c5098a44da"],
    "d2_shape": ["44bc8c39d7c165f0", "0efb4a3036be2cba", "08115d588122bdcd"],
    "d2_style": ["c552123fd0214a6c", "d1088215fb2bde0a", "a4d349a6328d2f6a"],
    "d2_style_shape": ["f3e8a221d211371e", "c52bdadf59bcf7e3", "07170a18d49fcf91"],
    "pipeline": ["b172e2ed010f934d", "6507019aeffecdb3", "e849578bebe70ced"],
    "pipeline_shape": ["02d0c016e767da2f", "300f7a945c90dc52", "5831dd22e317483b"],
}


def test_default_builds_are_unchanged() -> None:
    names = ("plate1x2", "plate2x4", "brick1x1", "brick1x2", "brick2x2", "brick2x4", "tile1x2")
    parts = part_tileset([CATALOG[n] for n in names], [RED, BLUE], empty_weight=0.5)
    style = StyleBias(StyleStats().add(tiny_model()), parts)
    inventory = {(n, c): 5 for n in names for c in ("red", "blue")}
    allowed = np.zeros((9, 7, 7), dtype=bool)
    allowed[:, 1:6, :] = True
    builders = {
        "d2": BottomUpBuilder(parts, any_offset=True),
        "d2_style": BottomUpBuilder(parts, any_offset=True, style=style),
        "pipeline": BottomUpBuilder(parts, any_offset=True, style=style, balanced=True, connect=True, connect_rounds=10),
    }
    for name, builder in builders.items():
        for suffix, target in (("", None), ("_shape", allowed)):
            grids = [builder.build((9, 7, 7), np.random.default_rng(s), inventory, target) for s in range(3)]
            assert all(check(g, parts, inventory) for g in grids)  # not empty, and valid
            digests = [hashlib.sha256(g.tobytes()).hexdigest()[:16] for g in grids]
            assert digests == DEFAULT_FINGERPRINTS[name + suffix], name + suffix
