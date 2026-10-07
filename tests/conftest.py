from pathlib import Path

import pytest

from brickwfc.tileset import Tileset, load_tileset

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


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
