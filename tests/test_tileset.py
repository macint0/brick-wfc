import json
from pathlib import Path

import numpy as np
import pytest

from brickwfc.tileset import OPPOSITE, Tileset, load_tileset, parse_hex_color


def allowed(ts: Tileset, a: str, b: str) -> bool:
    """True if a and b may touch in every direction (the JSON pairs are undirected)."""
    return bool(ts.compat[:, ts.index(a), ts.index(b)].all())


def test_terrain_rules(terrain: Tileset) -> None:
    assert terrain.names == ("water", "sand", "grass", "forest")
    for name in terrain.names:
        assert allowed(terrain, name, name)
    for a, b in [("water", "sand"), ("sand", "grass"), ("grass", "forest")]:
        assert allowed(terrain, a, b) and allowed(terrain, b, a)
    for a, b in [("water", "grass"), ("water", "forest"), ("sand", "forest")]:
        assert not terrain.compat[:, terrain.index(a), terrain.index(b)].any()
        assert not terrain.compat[:, terrain.index(b), terrain.index(a)].any()


def test_compat_is_symmetric(terrain: Tileset) -> None:
    for d in range(4):
        np.testing.assert_array_equal(terrain.compat[d], terrain.compat[OPPOSITE[d]].T)


def test_asymmetric_rules_rejected() -> None:
    compat = np.zeros((4, 2, 2), dtype=bool)
    compat[1, 0, 1] = True  # b east of a, but not a west of b
    with pytest.raises(ValueError, match="asymmetric"):
        Tileset(("a", "b"), ((0, 0, 0), (255, 255, 255)), np.ones(2), compat)


def test_directed_symmetric_rules_accepted() -> None:
    compat = np.zeros((4, 2, 2), dtype=bool)
    compat[1, 0, 1] = True  # b east of a
    compat[3, 1, 0] = True  # a west of b
    Tileset(("a", "b"), ((0, 0, 0), (255, 255, 255)), np.ones(2), compat)


def test_unknown_tile_in_pair_rejected() -> None:
    with pytest.raises(ValueError, match="unknown tile"):
        Tileset.from_pairs(["a"], [(0, 0, 0)], [1.0], [("a", "zzz")])


@pytest.mark.parametrize("weight", [0.0, -1.0])
def test_nonpositive_weight_rejected(weight: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        Tileset.from_pairs(["a"], [(0, 0, 0)], [weight], [("a", "a")])


def test_tileset_is_read_only(terrain: Tileset) -> None:
    with pytest.raises(ValueError):
        terrain.compat[0, 0, 0] = False


def test_parse_hex_color() -> None:
    assert parse_hex_color("#2f6fc4") == (0x2F, 0x6F, 0xC4)
    with pytest.raises(ValueError):
        parse_hex_color("#fff")


def test_load_tileset_defaults_weight_to_one(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"tiles": [{"name": "a", "color": "#000000"}], "adjacency": [["a", "a"]]}))
    assert load_tileset(path).weights.tolist() == [1.0]
