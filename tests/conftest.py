import json
from pathlib import Path

import pytest

from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape
from brickwfc.bricks.style import StyleStats
from brickwfc.ldraw.export import write_ldr

from brickwfc.tileset import Tileset, load_tileset

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RED, BLUE, WHITE, YELLOW = colors_by_name(["red", "blue", "white", "yellow"])


@pytest.fixture
def terrain() -> Tileset:
    return load_tileset(EXAMPLES / "terrain.json")


@pytest.fixture
def three_coloring() -> Tileset:
    """Proper 3-coloring: no tile may touch itself. Contradicts on a fair share of 16x16 attempts."""
    return Tileset.from_pairs(
        ["a", "b", "c"],
        [(255, 0, 0), (0, 255, 0), (0, 0, 255)],
        [1.0, 1.0, 1.0],
        [("a", "b"), ("b", "c"), ("c", "a")],
    )


@pytest.fixture
def wsf() -> Tileset:
    """1D sanity tileset: W-S and S-F allowed, plus same-same; W-F forbidden."""
    return Tileset.from_pairs(
        ["W", "S", "F"],
        [(0, 0, 255), (255, 220, 120), (0, 120, 0)],
        [1.0, 1.0, 1.0],
        [("W", "W"), ("S", "S"), ("F", "F"), ("W", "S"), ("S", "F")],
    )


# M12: a tiny real-looking model, as an LDraw file, and synthetic M10 style statistics.


def piece(name: str, layer: int, x: int = 0, z: int = 0, color=RED, rotated: bool = False) -> PlacedPart:
    return PlacedPart(Shape(CATALOG[name], rotated), color, layer, x, z)


def tiny_model() -> list[PlacedPart]:
    """A small stable model: a floor of plates, a ring of bricks, a plate roof."""
    floor = [piece("plate2x4", 0, x, z, BLUE) for x in (0, 4) for z in (0, 2, 4)]
    walls = [piece("brick2x4", 1, 0, 0), piece("brick2x4", 1, 4, 4), piece("brick2x2", 1, 6, 0, YELLOW),
             piece("brick2x2", 1, 0, 4, YELLOW), piece("brick1x2", 1, 0, 2, RED, rotated=True)]
    roof = [piece("plate2x4", 4, x, z, WHITE) for x in (0, 4) for z in (0, 4)] + [piece("plate1x2", 5, 1, 1, RED)]
    return floor + walls + roof


@pytest.fixture
def tiny_ldr(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.ldr"
    write_ldr([p.placement() for p in tiny_model()], path, "tiny")
    with path.open("a", encoding="utf-8") as f:
        f.write("1 4 0 -8 0 1 0 0 0 1 0 0 0 1 3626b.dat\n")  # not in the catalog
    return path


@pytest.fixture
def style_dir(tmp_path: Path) -> tuple[Path, Path]:
    """Synthetic M10 fold files and set list (the real ones are results of a long run)."""
    directory = tmp_path / "style"
    stats = StyleStats().add(tiny_model())
    for i in range(4):
        stats.save(directory / f"style_fold{i}.json")
    sets_file = tmp_path / "sets.json"
    sets_file.write_text(json.dumps({"selected": [f"s{i}" for i in range(8)]}), encoding="utf-8")
    return directory, sets_file
