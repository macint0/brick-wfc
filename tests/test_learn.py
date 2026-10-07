from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from brickwfc.gridio import detect_scale, read_grid_csv, read_grid_png, write_grid_csv
from brickwfc.learn import Example, example_from_csv, example_from_png, learn_tileset, main
from brickwfc.render2d import save_png
from brickwfc.tileset import Tileset, load_tileset, save_tileset
from brickwfc.wfc import adjacency_violations, run

from conftest import EXAMPLES


def as_example(grid: np.ndarray, tileset: Tileset) -> Example:
    return Example(grid, tileset.names, tileset.colors)


# M2 "Done when": learning from an M1 output and regenerating gives the same rule set.
def test_learn_from_m1_output_recovers_rules(terrain: Tileset) -> None:
    m1 = run(terrain, 32, 32, seed=1).grid
    learned = learn_tileset(as_example(m1, terrain))
    assert learned.rules() == terrain.rules()

    regenerated = run(learned, 32, 32, seed=2).grid
    assert adjacency_violations(regenerated, learned) == 0
    relearned = learn_tileset(as_example(regenerated, learned))
    assert relearned.rules() == terrain.rules()


def test_learn_from_m1_png_recovers_rules(terrain: Tileset, tmp_path: Path) -> None:
    path = tmp_path / "m1.png"
    save_png(run(terrain, 32, 32, seed=1).grid, terrain, path)
    assert learn_tileset(example_from_png(path, terrain)).rules() == terrain.rules()


def test_weights_are_frequencies(terrain: Tileset) -> None:
    grid = np.array([[0, 0, 0], [0, 1, 1]])
    learned = learn_tileset(as_example(grid, terrain))
    assert learned.names == ("water", "sand")  # absent tiles dropped
    np.testing.assert_allclose(learned.weights, [4 / 6, 2 / 6])


def test_rules_are_directional(terrain: Tileset) -> None:
    # Columns: water | sand. Sand is only ever seen east of water.
    grid = np.array([[0, 1], [0, 1], [0, 1]])
    learned = learn_tileset(as_example(grid, terrain))
    assert learned.rules() == {
        ("water", "sand", "E"),
        ("sand", "water", "W"),
        ("water", "water", "N"),
        ("water", "water", "S"),
        ("sand", "sand", "N"),
        ("sand", "sand", "S"),
    }


def test_learned_island_has_no_forbidden_pairs(terrain: Tileset) -> None:
    learned = learn_tileset(example_from_csv(EXAMPLES / "island.csv", terrain))
    assert learned.rules() <= terrain.rules()


def test_tileset_json_roundtrip_with_directed_rules(terrain: Tileset, tmp_path: Path) -> None:
    learned = learn_tileset(as_example(np.array([[0, 1], [0, 1]]), terrain))
    path = tmp_path / "learned.json"
    save_tileset(learned, path)
    loaded = load_tileset(path)
    assert loaded.names == learned.names
    assert loaded.rules() == learned.rules()
    np.testing.assert_allclose(loaded.weights, learned.weights)


def test_png_roundtrip_detects_scale(terrain: Tileset, tmp_path: Path) -> None:
    grid = run(terrain, 10, 12, seed=0).grid
    path = tmp_path / "g.png"
    save_png(grid, terrain, path, scale=5)
    assert detect_scale(np.asarray(Image.open(path).convert("RGB"))) == 5
    example = example_from_png(path, terrain)
    np.testing.assert_array_equal(example.grid, grid)


def test_png_without_reference_names_tiles_by_color(tmp_path: Path) -> None:
    path = tmp_path / "two.png"
    Image.fromarray(np.array([[[255, 0, 0], [0, 0, 255]]], dtype=np.uint8)).save(path)
    example = example_from_png(path)
    assert example.names == ("#0000ff", "#ff0000")
    np.testing.assert_array_equal(example.grid, [[1, 0]])


def test_png_with_unknown_color_rejected(terrain: Tileset, tmp_path: Path) -> None:
    path = tmp_path / "odd.png"
    Image.fromarray(np.full((2, 2, 3), 7, dtype=np.uint8)).save(path)
    with pytest.raises(ValueError, match="not in the reference"):
        example_from_png(path, terrain)


def test_non_uniform_cells_rejected(tmp_path: Path) -> None:
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    rgb[0, 0] = 255
    path = tmp_path / "noisy.png"
    Image.fromarray(rgb).save(path)
    with pytest.raises(ValueError, match="uniform"):
        read_grid_png(path, scale=2)


def test_csv_roundtrip(tmp_path: Path) -> None:
    grid = np.array([[0, 1, 2], [3, 2, 1]])
    path = tmp_path / "g.csv"
    write_grid_csv(grid, path)
    np.testing.assert_array_equal(read_grid_csv(path), grid)


def test_learn_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_tiles, regen = tmp_path / "learned.json", tmp_path / "regen.png"
    args = ["--example", str(EXAMPLES / "island.csv"), "--tiles", str(EXAMPLES / "terrain.json"),
            "--out-tiles", str(out_tiles), "--regen", str(regen), "--size", "16x16"]
    assert main(args) == 0
    assert "rules match reference" in capsys.readouterr().out
    assert load_tileset(out_tiles).num_tiles == 4
    assert regen.exists()
