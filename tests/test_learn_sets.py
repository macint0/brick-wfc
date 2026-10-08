from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.learn_sets import learn_coverage, main, shares, top_colors
from brickwfc.bricks.parts import PLATE_FILES, PLATES, PlacedPart, Shape, extract_parts, part_tileset
from brickwfc.bricks.voxelize import axis_aligned_turn, tile_grid, voxelize
from brickwfc.ldraw.export import write_ldr
from brickwfc.ldraw.mpd import PartInstance, flatten
from brickwfc.wfc import run

RED, BLUE = colors_by_name(["red", "blue"])

MPD = """0 FILE main.ldr
0 Main model
1 4 0 0 0 1 0 0 0 1 0 0 0 1 sub.ldr
1 1 100 -24 0 0 0 1 0 1 0 -1 0 0 sub.ldr
0 NOFILE
0 FILE sub.ldr
1 16 10 -8 0 1 0 0 0 1 0 0 0 1 3023.dat
1 15 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
0 NOFILE
"""


def instance(part: str, x: float, y: float, z: float, rotation=np.eye(3), color: int = 4) -> PartInstance:
    return PartInstance(part, color, np.array([x, y, z], dtype=float), np.asarray(rotation, dtype=float))


def test_flatten_resolves_submodels_and_inherits_color() -> None:
    parts = flatten(MPD)
    assert [(p.part, p.color) for p in parts] == [("3023.dat", 4), ("3001.dat", 15), ("3023.dat", 1), ("3001.dat", 15)]
    np.testing.assert_allclose(parts[0].position, [10, -8, 0])
    # Second copy is turned 90 degrees: its local (10, -8, 0) lands at (100, -32, -10).
    np.testing.assert_allclose(parts[2].position, [100, -32, -10])


def test_flatten_plain_ldr() -> None:
    assert [p.part for p in flatten("0 x\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3024.DAT\n")] == ["3024.dat"]


def test_axis_aligned_turn() -> None:
    assert axis_aligned_turn(np.eye(3)) is False
    assert axis_aligned_turn([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]) is True
    assert axis_aligned_turn([[-1, 0, 0], [0, 1, 0], [0, 0, -1]]) is False  # 180 degrees: same footprint
    assert axis_aligned_turn([[1, 0, 0], [0, -1, 0], [0, 0, -1]]) is None  # upside down
    c = np.cos(np.pi / 4)
    assert axis_aligned_turn([[c, 0, c], [0, 1, 0], [-c, 0, c]]) is None  # 45 degrees


def test_voxelize_counts_what_it_skips() -> None:
    placed, report = voxelize([
        instance("3020.dat", 30, -8, 10),  # 2x4 at x 0..3, z 0..1, layer 0
        instance("3024.dat", 0, -16, 0),  # 1x1 on top, layer 1
        instance("3024.dat", 0, -16, 0),  # same spot again
        instance("3024.dat", 5, -16, 0),  # quarter-stud off
        instance("3001.dat", 0, 0, 0),  # a brick: not one of the four M7 plates
        instance("3024.dat", 0, -8, 0, rotation=[[1, 0, 0], [0, -1, 0], [0, 0, -1]]),  # upside down
    ], PLATE_FILES)
    assert [(p.shape.name, p.layer, p.x, p.z) for p in placed] == [("plate2x4", 0, 0, 0), ("plate1x1", 1, 0, 0)]
    assert (report.overlapping, report.off_grid, report.unrecognized, report.tilted) == (1, 1, 1, 1)


def test_export_then_voxelize_roundtrip(tmp_path: Path) -> None:
    parts = part_tileset(list(PLATES.values()), [RED, BLUE])
    grid = run(parts.tileset, (3, 6, 6), seed=4).grid
    placed, _ = extract_parts(grid, parts)
    path = tmp_path / "b.ldr"
    write_ldr([p.placement() for p in placed], path, "roundtrip")
    recovered, report = voxelize(flatten(path.read_text()))
    assert report.kept == len(placed)

    def key(p: PlacedPart) -> tuple:
        return (p.shape.name, p.color.name, p.layer, p.x, p.z)

    # Voxelizing re-anchors at the build's minimum corner, so compare after the same shift.
    shift = (min(p.layer for p in placed), min(p.x for p in placed), min(p.z for p in placed))
    expected = sorted((s, c, y - shift[0], x - shift[1], z - shift[2]) for s, c, y, x, z in map(key, placed))
    assert sorted(map(key, recovered)) == expected


def test_tile_grid_roundtrip() -> None:
    placed = [PlacedPart(Shape(PLATES["plate2x4"], True), RED, 0, 0, 0), PlacedPart(Shape(PLATES["plate1x2"], False), BLUE, 1, 0, 0)]
    parts = part_tileset(list(PLATES.values()), [RED, BLUE])
    grid = tile_grid(placed, parts)
    assert grid.shape == (2, 4, 2)
    recovered, errors = extract_parts(grid, parts)
    assert errors == [] and sorted(recovered, key=lambda p: p.layer) == placed


def test_learn_coverage_counts_cells() -> None:
    model = [PlacedPart(Shape(PLATES["plate2x4"], False), RED, 0, 0, 0), PlacedPart(Shape(PLATES["plate1x1"], False), BLUE, 1, 0, 0)]
    coverage, colors = learn_coverage([model, model, []])
    assert coverage == {("plate2x4", "red"): 16, ("plate1x1", "blue"): 2}
    assert {c.name for c in colors} == {"red", "blue"}
    kept, kept_colors = top_colors(coverage, colors, 1)
    assert kept == {("plate2x4", "red"): 16} and [c.name for c in kept_colors] == ["red"]
    assert shares(coverage, 0) == {"plate1x1": 2 / 18, "plate2x4": 16 / 18}


def test_coverage_weights_shape_the_tileset() -> None:
    coverage = {("plate2x4", "red"): 3.0, ("plate1x1", "blue"): 1.0}
    parts = part_tileset(list(PLATES.values()), [RED, BLUE], coverage=coverage)
    names = parts.tileset.names
    assert not any("plate2x2" in n or "plate1x2" in n for n in names)  # unseen pairs get no tiles
    w = dict(zip(names, parts.tileset.weights))
    # Cell share 3:1 -> each of the 8 cells of a 2x4 weighs 3/8 of a 1x1 cell... before normalizing.
    assert w["plate2x4_x0z0_red"] * 8 / w["plate1x1_x0z0_blue"] == pytest.approx(3.0)
    assert sum(w[n] for n in names if n != "empty") == pytest.approx(len(PLATES))


def test_learn_sets_cli_offline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "omr"
    data.mkdir()
    for i in range(2):  # already-downloaded files are used without network access
        (data / f"fake-{i}.mpd").write_text(MPD.replace("3001.dat", "3020.dat"))
    args = ["--sets", "fake-0", "fake-1", "--data", str(data), "--size", "4x4x3", "--runs", "2", "--out", str(tmp_path / "m7")]
    assert main(args) == 0
    out = capsys.readouterr().out
    assert "learned from 2 sets" in out and "L1 to learned" in out
    assert (tmp_path / "m7" / "learned.json").exists()
