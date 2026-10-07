from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import PLATES, PartSet, PlacedPart, Shape, TileInfo, extract_parts, part_tileset
from brickwfc.ldraw.export import parse_ldr
from brickwfc.bricks.build import export_build
from brickwfc.tileset import load_tileset, save_tileset
from brickwfc.wfc import Wave, adjacency_violations, run


@pytest.fixture(scope="module")
def parts() -> PartSet:
    return part_tileset(list(PLATES.values()), colors_by_name(["red", "blue"]))


def test_tile_count(parts: PartSet) -> None:
    # empty + per color: 1x1 (1) + 1x2 (2 cells x 2 rotations) + 2x2 (4) + 2x4 (8 x 2)
    assert parts.tileset.num_tiles == 1 + 2 * (1 + 4 + 4 + 16)


def test_footprint() -> None:
    info = TileInfo(Shape(PLATES["plate2x4"], rotated=False), offset_x=1, offset_z=1)
    assert sorted(info.footprint()) == sorted((dz, dx) for dz in (-1, 0) for dx in (-1, 0, 1, 2))
    rotated = Shape(PLATES["plate2x4"], rotated=True)
    assert (rotated.size_x, rotated.size_z) == (2, 4)


def test_integrity_rules(parts: PartSet) -> None:
    rules = parts.tileset.rules()
    a, b = "plate1x2_x0z0_red", "plate1x2_x1z0_red"
    assert (a, b, "E") in rules
    assert (a, "empty", "E") not in rules  # the second half of a 1x2 must follow
    assert (a, "plate1x2_x1z0_blue", "E") not in rules  # same color
    assert (a, "empty", "W") in rules
    assert (a, "plate1x2_x0z0_red", "W") not in rules  # west neighbor's east side would be mid-part


def test_border_keeps_parts_inside(parts: PartSet) -> None:
    wave = Wave(parts.tileset, (1, 2, 2))
    names = parts.tileset.names
    # The east column cannot start a 1x2 (its second cell would be outside the grid).
    allowed_east = {names[t] for t in np.nonzero(wave.domain[0, 0, 1])[0]}
    assert "plate1x2_x0z0_red" not in allowed_east
    assert "plate1x2_x1z0_red" in allowed_east


# M5 "Done when": piece integrity on 100 random builds.
def test_100_random_builds_have_whole_parts(parts: PartSet) -> None:
    sizes_seen = set()
    for seed in range(100):
        grid = run(parts.tileset, (3, 6, 6), seed).grid
        assert grid is not None
        assert adjacency_violations(grid, parts.tileset) == 0
        placed, errors = extract_parts(grid, parts)
        assert errors == [], f"seed {seed}: {errors}"
        assert sum(len(p.cells()) for p in placed) == parts.solid[grid].sum()
        sizes_seen |= {p.shape.name for p in placed}
    assert sizes_seen == {"plate1x1", "plate1x2", "plate1x2_r90", "plate2x2", "plate2x4", "plate2x4_r90"}


def test_extract_parts_reports_broken_part(parts: PartSet) -> None:
    grid = np.zeros((1, 1, 2), dtype=np.int64)
    grid[0, 0, 0] = parts.tileset.index("plate1x2_x0z0_red")  # second half missing
    placed, errors = extract_parts(grid, parts)
    assert not placed and len(errors) == 2  # incomplete part + uncovered cell


def test_placement_centers_and_rotation() -> None:
    color = colors_by_name(["red"])[0]
    flat = PlacedPart(Shape(PLATES["plate2x4"], False), color, layer=1, x=2, z=3).placement()
    assert flat.position == (20 * 3.5, -16, 20 * 3.5) and flat.part == "3020.dat"
    assert flat.rotation == (1, 0, 0, 0, 1, 0, 0, 0, 1)
    turned = PlacedPart(Shape(PLATES["plate2x4"], True), color, layer=0, x=0, z=0).placement()
    assert turned.position == (10, -8, 30)
    assert turned.rotation == (0, 0, 1, 0, 1, 0, -1, 0, 0)


def test_export_writes_one_line_per_part(parts: PartSet, tmp_path: Path) -> None:
    grid = run(parts.tileset, (3, 6, 6), seed=0).grid
    placed, _ = extract_parts(grid, parts)
    export_build(grid, placed, parts, tmp_path / "b.ldr", tmp_path / "b.png", "test")
    assert len(parse_ldr((tmp_path / "b.ldr").read_text())) == len(placed)
    assert (tmp_path / "b.png").exists()


def test_border_survives_json_roundtrip(parts: PartSet, tmp_path: Path) -> None:
    save_tileset(parts.tileset, tmp_path / "parts.json")
    loaded = load_tileset(tmp_path / "parts.json")
    np.testing.assert_array_equal(loaded.border, parts.tileset.border)
