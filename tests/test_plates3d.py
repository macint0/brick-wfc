from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.__main__ import main
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import PLATES, PartSet, extract_parts, part_tileset
from brickwfc.bricks.support import floating_cells
from brickwfc.ldraw.export import parse_ldr, write_ldr
from brickwfc.render3d import render_voxels
from brickwfc.tileset import GRID2D, GRID3D, load_tileset, save_tileset
from brickwfc.wfc import adjacency_violations, run


RED, BLUE = "plate1x1_x0z0_red", "plate1x1_x0z0_blue"


@pytest.fixture
def plates() -> PartSet:
    """M4 tileset: 1x1 plates only, each cell must rest on a plate or the ground."""
    return part_tileset([PLATES["plate1x1"]], colors_by_name(["red", "blue"]), empty_weight=2.0, support="cell")


@pytest.mark.parametrize("topology", [GRID2D, GRID3D])
def test_topology_opposites_cancel(topology) -> None:
    for d, offset in enumerate(topology.offsets):
        opposite = topology.offsets[topology.opposite[d]]
        assert all(a + b == 0 for a, b in zip(offset, opposite))
    assert len(topology.forward) == topology.ndim


def test_plate_rules(plates: PartSet) -> None:
    rules = plates.tileset.rules()
    assert ("empty", RED, "U") not in rules  # nothing floats on air
    assert (RED, "empty", "D") not in rules
    assert (RED, BLUE, "U") in rules
    assert (RED, "empty", "U") in rules
    assert ("empty", BLUE, "E") in rules


def test_floating_cells() -> None:
    filled = np.zeros((3, 1, 2), dtype=bool)
    filled[0, 0, 0] = filled[1, 0, 0] = True  # supported column
    filled[2, 0, 1] = True  # floating
    np.testing.assert_array_equal(np.argwhere(floating_cells(filled)), [[2, 0, 1]])


def test_generated_builds_have_no_floating_plates(plates: PartSet) -> None:
    for seed in range(30):
        grid = run(plates.tileset, (5, 6, 6), seed).grid
        assert grid is not None
        assert adjacency_violations(grid, plates.tileset) == 0
        assert not floating_cells(plates.solid[grid]).any()
        assert plates.solid[grid].any()


def test_ldraw_placements(plates: PartSet, tmp_path: Path) -> None:
    grid = np.zeros((2, 1, 2), dtype=np.int64)  # (y, z, x)
    grid[0, 0, 1] = plates.tileset.index(RED)
    grid[1, 0, 1] = plates.tileset.index(BLUE)
    placed, errors = extract_parts(grid, plates)
    assert not errors
    placements = [p.placement() for p in placed]
    assert [(p.color, p.position, p.part) for p in placements] == [
        (4, (20, -8, 0), "3024.dat"),  # layer 0: top face 8 LDU above the ground (-Y is up)
        (1, (20, -16, 0), "3024.dat"),
    ]
    path = tmp_path / "b.ldr"
    write_ldr(placements, path, "test")
    assert parse_ldr(path.read_text()) == placements


def test_3d_tileset_json_roundtrip(plates: PartSet, tmp_path: Path) -> None:
    path = tmp_path / "plates.json"
    save_tileset(plates.tileset, path)
    loaded = load_tileset(path)
    assert loaded.topology == GRID3D
    assert loaded.rules() == plates.tileset.rules()


def test_render_voxels(plates: PartSet) -> None:
    grid = run(plates.tileset, (3, 4, 4), seed=0).grid
    colors = np.array(plates.tileset.colors, dtype=np.uint8)[grid]
    image = render_voxels(plates.solid[grid], colors)
    assert len(set(image.getdata())) > 3  # something besides the background was drawn


def test_cli_writes_ldr_and_png(tmp_path: Path) -> None:
    assert main(["--size", "5x4x3", "--runs", "2", "--out", str(tmp_path)]) == 0
    for seed in (0, 1):
        assert parse_ldr((tmp_path / f"build_seed{seed}.ldr").read_text())
        assert (tmp_path / f"build_seed{seed}.png").exists()
