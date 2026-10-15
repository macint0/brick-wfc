"""M12b step 2: training windows (training/data.py, numpy only) agree with the token format."""

import sys
from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.parts import PlacedPart
from brickwfc.bricks.tokens import PREFIX, build_vocab, encode, patches, symmetries
from brickwfc.experiments import export_tokens
from conftest import piece, tiny_model

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
import data  # noqa: E402


def exported(tmp_path: Path) -> tuple[data.Split, list]:
    vocab = build_vocab()
    vocab.save(tmp_path / "vocab.json")
    seqs, encoded = export_tokens.empty(), []
    for k, variant in enumerate(symmetries(tiny_model(), 3)):
        encoded.append(encode(variant, vocab, "set"))
        export_tokens.add(seqs, variant, encoded[-1], "set", 1, f"t/sym{k}")
    encoded.append(encode(tiny_model()[:5], vocab, "brickgpt", colorless=True))
    export_tokens.add(seqs, tiny_model()[:5], encoded[-1], "brickgpt", -1, "g")
    seqs.save(tmp_path / "train.npz", vocab)
    return data.Split(tmp_path / "train.npz", data.Vocab.load(tmp_path / "vocab.json")), encoded


def test_constants_match_the_token_format() -> None:
    assert data.PREFIX == PREFIX


def test_windows_match_encoded_tokens(tmp_path: Path) -> None:
    split, encoded = exported(tmp_path)
    vocab = build_vocab()
    ids, mask = split.window(0, 0, 100, drop_mask=False)
    assert ids.tolist() == encoded[0].tokens(vocab)
    assert np.array_equal(mask, patches(encoded[0].mask))
    n = split.size(0)
    ids, _ = split.window(0, 3, 4, drop_mask=False)
    assert ids[0] == vocab.id("CONT") and len(ids) == PREFIX + 4 * 5  # no EOS: the window stops early
    assert ids[PREFIX:].tolist() == encoded[0].parts[3:7].ravel().tolist()
    ids, mask = split.window(0, n - 2, 4, drop_mask=True)
    assert ids[-1] == vocab.id("EOS") and ids[3] == vocab.id("NOMASK") and not mask.any()


def test_sampler_is_seeded_and_mixes_sources(tmp_path: Path) -> None:
    split, _ = exported(tmp_path)
    sampler = data.Sampler(split, max_len=PREFIX + 1 + 5 * 6, set_share=0.5, mask_drop=0.3)
    a = sampler.batch(16, np.random.default_rng(3))
    b = sampler.batch(16, np.random.default_rng(3))
    assert all(np.array_equal(x, y) for x, y in zip(a, b))
    ids, masks = sampler.batch(200, np.random.default_rng(4))
    assert ids.shape[1] <= PREFIX + 1 + 5 * 6 and masks.shape == (200, 64, 125)
    sources = ids[:, 1]
    vocab = build_vocab()
    share = (sources == vocab.id("SRC_set")).mean()
    assert 0.35 < share < 0.65
    assert 0.15 < (ids[:, 3] == vocab.id("NOMASK")).mean() < 0.45


def test_eval_windows_cover_every_part(tmp_path: Path) -> None:
    split, _ = exported(tmp_path)
    max_len = PREFIX + 1 + 5 * 6
    windows = data.eval_windows(split, max_len)
    first = [ids for ids, _ in windows if ids[0] == build_vocab().id("BOS")]
    assert len(first) == len(split)
    assert all(len(ids) <= max_len for ids, _ in windows)


def test_val_sets_are_held_out_of_sampling(tmp_path: Path) -> None:
    split, _ = exported(tmp_path)  # builds 0-2: set "t" in 3 symmetries; build 3: a BrickGPT structure
    every, identity = data.set_builds(split, ["t"])
    assert every == [0, 1, 2] and identity == [0]
    try:
        data.set_builds(split, ["nope"])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    sampler = data.Sampler(split, max_len=PREFIX + 1 + 5 * 6, set_share=0.5, mask_drop=0.0, exclude=every)
    ids, _ = sampler.batch(50, np.random.default_rng(0))
    vocab = build_vocab()
    assert (ids[:, 1] == vocab.id("SRC_brickgpt")).all()  # no window from the held-out set
    windows = data.eval_windows(split, PREFIX + 1 + 5 * 6, indices=identity)
    assert windows and all(w[0][1] == vocab.id("SRC_set") for w in windows)


# Translation jitter --------------------------------------------------------------------------------------


def moved(placed: list[PlacedPart], dz: int, dx: int) -> list[PlacedPart]:
    return [PlacedPart(p.shape, p.color, p.layer, p.x + dx, p.z + dz) for p in placed]


def split_of(tmp_path: Path, builds: list[list[PlacedPart]], source: str = "set") -> data.Split:
    vocab = build_vocab()
    vocab.save(tmp_path / "vocab.json")
    seqs = export_tokens.empty()
    for k, build in enumerate(builds):
        export_tokens.add(seqs, build, encode(build, vocab, source, colorless=source == "brickgpt"), source, 1, f"b{k}")
    seqs.save(tmp_path / "train.npz", vocab)
    return data.Split(tmp_path / "train.npz", data.Vocab.load(tmp_path / "vocab.json"))


SCALE_1 = tiny_model()  # 6 studs along z, 8 along x
SCALE_2 = tiny_model() + [piece("plate1x2", 0, 30, 0)]  # 32 studs along x: coarse voxels of 2 studs
SCALE_4 = tiny_model() + [piece("plate1x2", 0, 60, 0)]  # 62 studs along x: the 64-stud token grid binds along z
OFF_ORIGIN = moved(tiny_model(), 3, 5)  # a BrickGPT-like structure that does not touch the origin


def test_shift_ranges_keep_the_build_in_both_grids(tmp_path: Path) -> None:
    split = split_of(tmp_path, [SCALE_1, SCALE_2, SCALE_4, OFF_ORIGIN])
    assert split.scale.tolist() == [1, 2, 4, 1]
    assert split.shift_ranges([0, 1, 2, 3]).tolist() == [
        [0, 14, 0, 12],  # 6 + 14 = 8 + 12 = 20 voxels of 1 stud
        [0, 17, 0, 4],  # z: 6 studs = 3 voxels, + 17 = 20; x: 32 studs = 16 voxels, + 4 = 20
        [0, 14, 0, 0],  # z: 2 voxels, + 14 = 16 voxels = 64 studs (the token grid, before the mask's 20)
        [-3, 11, -5, 7],  # scale 1 also moves back to the origin
    ]


@pytest.mark.parametrize("build", [SCALE_1, SCALE_2, SCALE_4, OFF_ORIGIN])
def test_a_shifted_window_is_the_encoding_of_the_shifted_build(tmp_path: Path, build: list[PlacedPart]) -> None:
    """Tokens and mask patches move together, exactly as encode() writes the moved build; one voxel beyond the
    range, encode() would change the scale or leave the token grid."""
    split, vocab = split_of(tmp_path, [build]), build_vocab()
    s = int(split.scale[0])
    z_lo, z_hi, x_lo, x_hi = split.shift_ranges([0])[0].tolist()
    for kz, kx in [(z_lo, x_lo), (z_hi, x_hi), (z_lo, x_hi), (z_hi, x_lo), ((z_lo + z_hi) // 2, (x_lo + x_hi) // 2)]:
        ids, mask = split.window(0, 0, 1000, drop_mask=False, shift=(kz, kx))
        expected = encode(moved(build, kz * s, kx * s), vocab, "set")
        assert ids.tolist() == expected.tokens(vocab)
        assert np.array_equal(mask, patches(expected.mask))
        ids, _ = split.window(0, 3, 4, drop_mask=False, shift=(kz, kx))  # a later window moves the same way
        assert ids[PREFIX:].tolist() == expected.parts[3:7].ravel().tolist()
    for dz, dx in [((z_hi + 1) * s, 0), (0, (x_hi + 1) * s)]:
        try:
            assert encode(moved(build, dz, dx), vocab, "set").header[2] != vocab.id(f"SCALE_{s}")
        except ValueError:
            pass  # outside the token grid


def test_sampler_jitters_only_the_listed_sources(tmp_path: Path) -> None:
    vocab = build_vocab()
    vocab.save(tmp_path / "vocab.json")
    seqs = export_tokens.empty()
    for source, build in (("set", SCALE_1), ("brickgpt", OFF_ORIGIN)):
        export_tokens.add(seqs, build, encode(build, vocab, source), source, 1, source)
    seqs.save(tmp_path / "train.npz", vocab)
    split = data.Split(tmp_path / "train.npz", data.Vocab.load(tmp_path / "vocab.json"))
    max_len = PREFIX + 1 + 5 * 30

    def first_z(sampler: data.Sampler, seed: int) -> dict[str, set[int]]:
        ids, _ = sampler.batch(200, np.random.default_rng(seed))
        out: dict[str, set[int]] = {"SRC_set": set(), "SRC_brickgpt": set()}
        for row in ids:
            out[vocab.tokens[row[1]]].add(int(row[PREFIX + 1]))  # the first part's Z token
        return out

    plain = first_z(data.Sampler(split, max_len, 0.5, 0.2), 0)
    assert plain == {"SRC_set": {vocab.z(0)}, "SRC_brickgpt": {vocab.z(3)}}
    jittered = data.Sampler(split, max_len, 0.5, 0.2, jitter=["set"])
    seen = first_z(jittered, 0)
    assert seen["SRC_brickgpt"] == {vocab.z(3)} and seen["SRC_set"] == {vocab.z(z) for z in range(15)}  # 0..14
    assert first_z(jittered, 0) == seen  # seeded
    both = first_z(data.Sampler(split, max_len, 0.5, 0.2, jitter=["set", "brickgpt"]), 0)
    assert both["SRC_brickgpt"] == {vocab.z(z) for z in range(15)}  # Z 3 moves by -3..+11
    with pytest.raises(ValueError, match="unknown jitter sources"):
        data.Sampler(split, max_len, 0.5, 0.2, jitter=["sets"])
