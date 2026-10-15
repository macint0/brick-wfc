"""The M12e pool export (export_tokens --pool): crops, set splits, naming, the end-to-end export."""
import json
from pathlib import Path

import pytest

from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape
from brickwfc.bricks.tokens import encode, symmetries
from brickwfc.experiments import export_tokens
from brickwfc.experiments.omr_pool import catalog_fingerprint
from brickwfc.experiments.pool_tokens import PoolModel, anchored, crops, split_sets
from test_omr_pool import _model

(RED,) = colors_by_name(["red"])
PLATE = Shape(CATALOG["plate1x1"], False)


def _plate(layer: int, x: int, z: int) -> PlacedPart:
    return PlacedPart(PLATE, RED, layer, x, z)


def test_anchored_moves_the_min_corner_to_the_origin() -> None:
    moved = anchored([_plate(3, 5, 7), _plate(4, 6, 9)])
    assert [(p.layer, p.x, p.z) for p in moved] == [(0, 0, 0), (1, 1, 2)]


def test_crops_cut_large_builds_into_blocks_and_drop_small_ones() -> None:
    small = [_plate(0, x, 0) for x in range(5)]
    assert crops(small, min_parts=5) == [small] and crops(small, min_parts=6) == []
    wide = [_plate(0, x, 0) for x in range(10)] + [_plate(0, 70, 3)]
    blocks = crops(wide, min_parts=1, size_xz=8)
    assert [len(b) for b in blocks] == [8, 2, 1]  # x // 8 blocks: 0..7, 8..9, 70
    assert all(min(p.x for p in b) == 0 and min(p.z for p in b) == 0 for b in blocks)
    assert [len(b) for b in crops(wide, min_parts=2, size_xz=8)] == [8, 2]
    tall = [_plate(y, 0, 0) for y in range(5)]
    assert [len(b) for b in crops(tall, min_parts=1, size_y=3)] == [3, 2]


def test_crops_fit_the_token_grid_in_every_symmetry() -> None:
    """A part whose min corner is in a block but which sticks out of it is dropped: turned or mirrored, the block's
    extent decides where min corners land (the export failed with a brick2x2 at x = 78)."""
    brick = Shape(CATALOG["brick2x2"], False)
    across = PlacedPart(brick, RED, 0, 63, 0)  # covers x = 63..64, across the 64-stud edge
    build = [_plate(0, x, 1) for x in range(0, 100, 3)] + [across]
    blocks = crops(build, min_parts=1)
    assert sum(len(b) for b in blocks) == len(build) - 1 and across not in [p for b in blocks for p in b]
    vocab = export_tokens.build_vocab()
    for block in blocks:
        for variant in symmetries(block, 8):
            encode(variant, vocab, "set")  # raises if any min corner leaves the grid


def test_split_sets_holds_out_demo_sets_and_a_seeded_validation_share() -> None:
    sets = [f"{i}-1" for i in range(40)] + ["6378-1", "6378-1"]
    train, val, held = split_sets(sets, ["6378-1", "31048-1"], 0.05, seed=0)
    assert held == ["6378-1"] and len(val) == 2 and len(train) == 38
    assert not set(train) & set(val) and "6378-1" not in train + val
    assert split_sets(sets, ["6378-1"], 0.05, seed=0) == (train, val, held)
    assert split_sets(sets, ["6378-1"], 0.05, seed=1)[1] != val
    assert split_sets(["a", "b"], [], 0.0, seed=0) == (["a", "b"], [], [])


def test_pool_splits_name_crops_and_keep_symmetries_for_training_only() -> None:
    vocab = export_tokens.build_vocab()
    one = [_plate(0, x, 0) for x in range(3)]
    models = [PoolModel("1-1.mpd", "1-1", 3, 3, 3, [one]), PoolModel("2-1_B.mpd", "2-1", 6, 6, 6, [one, one]),
              PoolModel("3-1.mpd", "3-1", 3, 3, 3, [one])]
    out = export_tokens.pool_splits(models, {"2-1": "setval", "3-1": "heldout"}, 2, vocab)
    assert out["train"].name == ["1-1/sym0", "1-1/sym1"]
    assert out["setval"].name == ["2-1_B/c0/sym0", "2-1_B/c1/sym0"]
    assert out["heldout"].name == ["3-1/sym0"] and out["heldout"].fold == [2]


def _brickgpt(cache: Path) -> None:
    cache.mkdir()
    rows = [{"structure_id": "a1", "bricks": "2x4 (0,0,0)\n2x2 (0,0,1)"}, {"structure_id": "c3", "bricks": "1x1 (3,3,0)"}]
    for split in ("train", "test"):
        (cache / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _pool(tmp_path: Path, catalog: str) -> Path:
    omr = tmp_path / "omr"
    omr.mkdir()
    rows = []
    for i, number in enumerate(["6378-1", "1-1", "2-1", "3-1"]):
        (omr / f"{number}.mpd").write_text(_model(3 + i, 1), encoding="utf-8")
        rows.append({"set": number, "file": f"{number}.mpd", "parts": 4 + i, "recognized": 3 + i, "on_grid": 3 + i,
                     "selected": "yes"})
    (omr / "6378-1_B.mpd").write_text(_model(2, 0), encoding="utf-8")  # an alternate of a held-out set
    rows.append({"set": "6378-1", "file": "6378-1_B.mpd", "parts": 2, "recognized": 2, "on_grid": 2, "selected": "yes"})
    rows.append({"set": "9-1", "file": "9-1.mpd", "parts": 1, "recognized": 0, "on_grid": 0, "selected": "< 50% recognized"})
    pool = {"catalog": catalog, "catalog_parts": len(CATALOG), "thresholds": {}, "models": rows}
    path = tmp_path / "pool.json"
    path.write_text(json.dumps(pool), encoding="utf-8")
    return path


def test_export_pool_end_to_end(tmp_path: Path) -> None:
    _brickgpt(tmp_path / "bg")
    pool = _pool(tmp_path, catalog_fingerprint())
    out = tmp_path / "tokens"
    args = ["--pool", str(pool), "--omr", str(tmp_path / "omr"), "--brickgpt", str(tmp_path / "bg"), "--out", str(out),
            "--results", str(tmp_path / "r.md"), "--oov-results", str(tmp_path / "oov.md"), "--workers", "1",
            "--min-crop-parts", "1", "--val-share", "0.5", "--set-symmetries", "4", "--heldout-sets", "6378-1", "31048-1"]
    assert export_tokens.main(args) == 0
    assert sorted(p.name for p in out.iterdir()) == ["export.json", "heldout.npz", "setval.npz", "train.npz", "val.npz",
                                                  "vocab.json"]
    assert json.loads((out / "export.json").read_text(encoding="utf-8"))["catalog"] == catalog_fingerprint()
    held = export_tokens.load_npz(out / "heldout.npz")
    assert list(held["name"]) == ["6378-1/sym0", "6378-1_B/sym0"] and len(held["parts"]) == 3 + 2
    setval = export_tokens.load_npz(out / "setval.npz")
    train = export_tokens.load_npz(out / "train.npz")
    trained = {str(n).split("/")[0] for n, s in zip(train["name"], train["source"]) if s == "set"}
    validated = {str(n).split("/")[0] for n in setval["name"]}
    assert len(validated) == 2 and len(trained) == 1 and not trained & validated and "6378-1" not in trained | validated
    assert sum(s == "set" for s in train["source"]) == 4 and sum(s == "brickgpt" for s in train["source"]) == 2
    text = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "**5 models from 4 sets**" in text and "Not in the pool, so not exported: 31048-1" in text
    oov = (tmp_path / "oov.md").read_text(encoding="utf-8")
    assert "| 6378-1 | 6378-1 | heldout | 4 | 1 | 25.0 |" in oov


def test_export_pool_refuses_a_pool_from_another_catalog(tmp_path: Path) -> None:
    pool = _pool(tmp_path, "000000000000")
    with pytest.raises(SystemExit, match="rerun python -m brickwfc.experiments.omr_pool"):
        export_tokens.main(["--pool", str(pool), "--omr", str(tmp_path / "omr"), "--out", str(tmp_path / "t")])
