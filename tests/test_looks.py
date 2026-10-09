"""M12b step 3: skin preference and symmetric decoding in the bottom-up builder; mirror-preserving targets."""

from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from brickwfc.alt.target import load_target
from brickwfc.bricks.bottomup import BottomUpBuilder
from brickwfc.bricks.parts import CATALOG, extract_parts, part_tileset
from brickwfc.bricks.skin import skin
from brickwfc.bricks.support import is_stable
from brickwfc.bricks.symmetry import mirror_plane, part_symmetry, reflected
from conftest import BLUE, RED

NAMES = ("plate1x1", "plate1x2", "plate2x2", "plate2x4", "brick1x1", "brick1x2", "brick2x2", "brick2x4",
         "plate2x2_corner", "slope45_2x2", "tile1x2")


@pytest.fixture(scope="module")
def parts():
    return part_tileset([CATALOG[n] for n in NAMES], [RED, BLUE], empty_weight=0.05)


def target() -> np.ndarray:
    """A stepped block, symmetric across x = 4.5 (x 1..8) on a 10-wide grid, not across z (the step is at the back)."""
    mask = np.zeros((9, 6, 10), dtype=bool)
    mask[:6, :, 1:9] = True
    mask[6:, 0:3, 3:7] = True
    return mask


def check(grid: np.ndarray, parts, allowed: np.ndarray, inventory: dict | None = None) -> list:
    placed, errors = extract_parts(grid, parts)
    assert not errors
    assert all(allowed[c] for p in placed for c in p.cells())
    assert is_stable(placed, parts.solid[grid])
    if inventory is not None:
        used = Counter((p.shape.part.name, p.color.name) for p in placed)
        assert all(n <= inventory.get(k, 0) for k, n in used.items())
    return placed


def test_skin_preference_shows_larger_parts(parts) -> None:
    mask = target()
    per_part = {}
    for skin_on in (False, True):
        builder = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True, skin=skin_on)
        values = []
        for seed in range(8):
            placed = check(builder.build(mask.shape, np.random.default_rng(seed), allowed=mask), parts, mask)
            values.append(skin(placed, mask.shape).faces_per_part)
        per_part[skin_on] = np.mean(values)
    assert per_part[True] > per_part[False]


def test_symmetric_decoding_mirrors_parts_and_keeps_the_rules(parts) -> None:
    mask = target()
    plane = mirror_plane(mask)
    assert plane is not None and (plane.axis, plane.total) == (2, 9)
    inventory = {(n, c.name): 12 for n in NAMES for c in (RED, BLUE)}
    shares = {}
    for symmetric in (False, True):
        builder = BottomUpBuilder(parts, any_offset=True, balanced=True, open_tops=True)
        values = []
        for seed in range(8):
            grid = builder.build(mask.shape, np.random.default_rng(seed), inventory, mask,
                                 plane=plane if symmetric else None)
            placed = check(grid, parts, mask, inventory)
            values.append(part_symmetry(placed, plane, mask.shape).parts)
        shares[symmetric] = np.mean(values)
    assert shares[True] > 0.7 > shares[False]


def test_symmetric_decoding_respects_a_short_inventory(parts) -> None:
    mask = target()
    inventory = {("brick2x2", "red"): 3, ("plate1x2", "blue"): 5}
    builder = BottomUpBuilder(parts, any_offset=True, balanced=True)
    for seed in range(5):
        check(builder.build(mask.shape, np.random.default_rng(seed), inventory, mask, plane=mirror_plane(mask)),
              parts, mask, inventory)


def test_options_off_reproduce_builds(parts) -> None:
    mask = target()
    plain = BottomUpBuilder(parts, any_offset=True, balanced=True)
    off = BottomUpBuilder(parts, any_offset=True, balanced=True, skin=False)
    for seed in range(3):
        a = plain.build(mask.shape, np.random.default_rng(seed), allowed=mask)
        b = off.build(mask.shape, np.random.default_rng(seed), allowed=mask, plane=None)
        assert (a == b).all()


def test_symmetric_target_has_a_plane_and_mirrored_supports(tmp_path: Path) -> None:
    # A bench symmetric across x, not across z (legs and a backrest at the front), in BrickGPT's format.
    text = "1x1 (2,1,0)\n1x1 (9,1,0)\n1x1 (2,1,1)\n1x1 (9,1,1)\n" + "".join(
        f"8x1 (0,{y},2)\n4x1 (8,{y},2)\n" for y in range(9)) + "".join(
        f"8x1 (0,{y},{z})\n4x1 (8,{y},{z})\n" for y in range(2) for z in (3, 4))
    path = tmp_path / "table.txt"
    path.write_text(text, encoding="utf-8")
    plain = load_target(str(path), 1500, [RED])
    sym = load_target(str(path), 1500, [RED], supports=True, symmetric=True)
    assert plain.plane is None and sym.plane is not None and sym.plane.axis == 2
    assert sym.plane.score == 1.0 and (reflected(sym.mask, sym.plane) == sym.mask).all()
    assert (sym.mask >= plain.mask).all()  # symmetrized by adding cells, never removing them
    assert "mirror plane" in sym.description
