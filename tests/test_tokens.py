"""M12b step 2: builds as token sequences, symmetries, coarse masks, dataset export."""

import json
from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.brickgpt import parse, to_placed
from brickwfc.bricks.tokens import (MASK_GRID, MASK_PATCHES, PART_TOKENS, PATCH_BITS, PREFIX, Vocab, build_vocab,
                                    coarse_mask, decode_part, encode, mask_scale, mirror_x, occupancy, ordered,
                                    patches, raster_key, rotate90, symmetries)
from brickwfc.experiments import export_tokens
from conftest import RED, piece, tiny_model


def test_vocab_is_complete_and_round_trips(tmp_path: Path) -> None:
    vocab = build_vocab(["ldraw484", "red"])
    assert vocab.id("C:ldraw484") and vocab.id("C:NONE") and vocab.id("S:brick2x4_r90") and vocab.id("S:plate1x1")
    assert vocab.id("SCALE_1") and vocab.y(191) and vocab.z(63) and vocab.x(0)
    assert len(vocab.color_ids()) == len(set(vocab.color_ids()))
    vocab.save(tmp_path / "v.json")
    assert Vocab.load(tmp_path / "v.json") == vocab
    assert vocab.color(RED) == vocab.id("C:red")
    assert vocab.color(type(RED)("magenta", 26, (1, 2, 3))) == vocab.id("C:OTHER")


def test_encode_orders_parts_raster_and_decodes_back() -> None:
    vocab = build_vocab()
    model = tiny_model()
    encoded = encode(model[::-1], vocab, "set")
    assert encoded.parts.shape == (len(model), PART_TOKENS)
    decoded = [decode_part(row, vocab) for row in encoded.parts]
    assert decoded == ordered(model)
    assert [raster_key(p) for p in decoded] == sorted(raster_key(p) for p in decoded)
    tokens = encoded.tokens(vocab)
    assert len(tokens) == PREFIX + PART_TOKENS * len(model) + 1
    assert tokens[0] == vocab.id("BOS") and tokens[1] == vocab.id("SRC_set") and tokens[-1] == vocab.id("EOS")


def test_brickgpt_structures_encode_colorless() -> None:
    vocab = build_vocab()
    placed = to_placed(parse("2x4 (0,0,0)\n1x2 (5,3,0)\n2x2 (0,0,1)"), RED)
    encoded = encode(placed, vocab, "brickgpt", colorless=True)
    assert set(encoded.parts[:, 4].tolist()) == {vocab.id("C:NONE")}
    assert encoded.header[1] == vocab.id("SRC_brickgpt") and encoded.header[2] == vocab.id("SCALE_1")
    # Brick on layer 1 of BrickGPT's grid sits on plate layer 3.
    assert encoded.parts[-1, 0] == vocab.y(3)


def test_symmetries_preserve_the_build() -> None:
    model = tiny_model()
    cells = occupancy(model)
    variants = symmetries(model)
    assert len(variants) == 8 and variants[0] == model
    for v in variants:
        occ = occupancy(v)
        assert occ.sum() == cells.sum() and sorted(occ.shape) == sorted(cells.shape) and occ.shape[0] == cells.shape[0]
        assert sum(p.shape.cells for p in v) == occ.sum()  # no overlaps
    turned = model
    for _ in range(4):
        turned = rotate90(turned)
    assert turned == model
    assert mirror_x(mirror_x(model)) == model
    # A quarter turn swaps the footprint and turns 1x2 parts.
    one = [piece("plate1x2", 0, 0, 0)]
    assert rotate90(one)[0].shape.rotated and (rotate90(one)[0].shape.size_x, rotate90(one)[0].shape.size_z) == (1, 2)


def test_rotation_matches_numpy_rot90() -> None:
    model = tiny_model()
    cells = occupancy(model)
    # (x, z) -> (Z - 1 - z, x): new[y, x, Z-1-z] = old[y, z, x], i.e. rot90 over (z, x).
    expected = np.rot90(cells, k=-1, axes=(1, 2))
    assert np.array_equal(occupancy(rotate90(model)), expected)
    assert np.array_equal(occupancy(mirror_x(model)), cells[:, :, ::-1])


def test_coarse_mask_scale_and_pooling() -> None:
    assert mask_scale((60, 20, 20)) == 1
    assert mask_scale((61, 20, 20)) == 2 and mask_scale((30, 21, 5)) == 2 and mask_scale((139, 32, 46)) == 3
    with pytest.raises(ValueError):
        mask_scale((10, 200, 10))
    cells = np.zeros((6, 4, 4), dtype=bool)
    cells[4, 3, 1] = True
    scale, mask = coarse_mask(cells)
    assert scale == 1 and mask.shape == (MASK_GRID,) * 3
    assert mask.sum() == 1 and mask[1, 3, 1]  # plate layer 4 is in coarse layer 1 (3 plates each)
    cells = np.zeros((70, 40, 30), dtype=bool)
    cells[69, 39, 29] = True
    scale, mask = coarse_mask(cells)
    assert scale == 2 and mask[69 // 6, 39 // 2, 29 // 2] and mask.sum() == 1


def test_patches_layout() -> None:
    assert patches(None).shape == (MASK_PATCHES, PATCH_BITS) and not patches(None).any()
    mask = np.zeros((MASK_GRID,) * 3, dtype=bool)
    mask[7, 2, 13] = True  # patch (1, 0, 2), inside (2, 2, 3)
    p = patches(mask)
    assert p.sum() == 1 and p[1 * 16 + 0 * 4 + 2, 2 * 25 + 2 * 5 + 3] == 1


def test_export_splits_and_report(tmp_path: Path) -> None:
    vocab = build_vocab()
    models = {f"s{i}": tiny_model() for i in range(4)}
    fold_of = {"s0": 0, "s1": 1, "s2": 0, "s3": 2}
    train, held = export_tokens.set_splits(models, fold_of, 0, 8, vocab)
    assert held.name == ["s0", "s2"] and len(train.encoded) == 2 * 8
    cache = tmp_path / "bg"
    cache.mkdir()
    rows = [{"structure_id": "a1", "bricks": "2x4 (0,0,0)\n2x2 (0,0,1)"},
            {"structure_id": "b2", "bricks": "2x4 (0,0,0)\n2x2 (0,0,0)"},  # overlapping: skipped
            {"structure_id": "c3", "bricks": "1x1 (3,3,0)"}]
    (cache / "train.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    gpt, skipped = export_tokens.brickgpt_split("train", cache, [], workers=1, chunk=2)
    gpt_first = to_placed(parse(rows[0]["bricks"]), export_tokens.GRAY)
    assert skipped == 1 and gpt.name == ["a1", "c3"]
    splits = {"train": export_tokens.merge(gpt, train), "val": gpt, "heldout": held}
    for name, seqs in splits.items():
        seqs.save(tmp_path / f"{name}.npz", vocab)
    data = export_tokens.load_npz(tmp_path / "train.npz")
    assert data["header"].shape == (18, 4) and data["masks"].shape == (18, 20, 20, 20)
    assert data["offsets"][-1] == len(data["parts"]) == 2 + 1 + 16 * len(tiny_model())
    assert np.array_equal(data["masks"][0], encode(gpt_first, vocab, "brickgpt", colorless=True).mask)
    assert list(data["source"][:2]) == ["brickgpt", "brickgpt"] and data["fold"][0] == -1
    text = export_tokens.report(splits, vocab, ["s0", "s2"], 8, {"train": 1, "test": 0}, 0, 4, 0)
    assert "Held out (fold 0):** s0, s2" in text and "8 horizontal symmetries" in text and "brick2x4" in text


def test_windows_count() -> None:
    per = (export_tokens.MAX_LEN - PREFIX - 1) // PART_TOKENS
    assert export_tokens.windows(10) == 1 and export_tokens.windows(per) == 1
    assert export_tokens.windows(per + 1) == 2 and export_tokens.windows(per + per // 2 + 1) == 3


def test_add_keeps_the_mask_packed_and_saves_the_same_bytes(tmp_path: Path) -> None:
    """Sequences hold each mask packed from the moment it is added (memory); the saved masks are the bytes packing
    the full mask at save time gave before."""
    vocab = build_vocab()
    seqs = export_tokens.empty()
    full = [encode(v, vocab, "set") for v in symmetries(tiny_model(), 4)]
    for k, (variant, e) in enumerate(zip(symmetries(tiny_model(), 4), full)):
        export_tokens.add(seqs, variant, e, "set", 0, f"t/sym{k}")
    assert all(e.mask is None for e in seqs.encoded) and all(m.dtype == np.uint8 and m.shape == (1000,) for m in seqs.masks)
    seqs.save(tmp_path / "t.npz", vocab)
    with np.load(tmp_path / "t.npz") as saved:
        assert np.array_equal(saved["masks"], np.stack([np.packbits(e.mask.ravel()) for e in full]))
    merged = export_tokens.merge(seqs, seqs)
    assert len(merged.masks) == len(merged.encoded) == 8
