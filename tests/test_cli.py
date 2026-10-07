import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from brickwfc.render2d import render
from brickwfc.run import main, parse_size
from brickwfc.tileset import Tileset

from conftest import EXAMPLES


def test_render_colors_and_scale(terrain: Tileset) -> None:
    grid = np.array([[0, 1], [2, 3]])
    img = render(grid, terrain, scale=4)
    assert img.size == (8, 8)
    assert img.getpixel((0, 0)) == terrain.colors[0]
    assert img.getpixel((7, 0)) == terrain.colors[1]
    assert img.getpixel((0, 7)) == terrain.colors[2]
    assert img.getpixel((7, 7)) == terrain.colors[3]


def test_parse_size() -> None:
    assert parse_size("32x16") == (32, 16)


def test_cli_writes_png(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "m1.png"
    code = main(["--tiles", str(EXAMPLES / "terrain.json"), "--size", "12x10", "--seed", "1", "--out", str(out)])
    assert code == 0
    assert Image.open(out).size == (12 * 8, 10 * 8)
    assert "seed=1 ok" in capsys.readouterr().out


def test_cli_multiple_runs_writes_stats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    stats_path = tmp_path / "stats.json"
    args = ["--tiles", str(EXAMPLES / "terrain.json"), "--size", "8x8", "--runs", "5", "--stats", str(stats_path)]
    assert main(args) == 0
    assert "success rate:        100.0% (5/5)" in capsys.readouterr().out
    stats = json.loads(stats_path.read_text())
    assert [s["seed"] for s in stats] == [0, 1, 2, 3, 4]
