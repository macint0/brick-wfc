"""M12b step 2: training windows (training/data.py, numpy only) agree with the token format."""

import sys
from pathlib import Path

import numpy as np

from brickwfc.bricks.tokens import PREFIX, build_vocab, encode, patches, symmetries
from brickwfc.experiments import export_tokens
from conftest import tiny_model

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
import data  # noqa: E402


def exported(tmp_path: Path) -> tuple[data.Split, list]:
    vocab = build_vocab()
    vocab.save(tmp_path / "vocab.json")
    seqs = export_tokens.empty()
    for k, variant in enumerate(symmetries(tiny_model(), 3)):
        export_tokens.add(seqs, variant, encode(variant, vocab, "set"), "set", 1, f"t/sym{k}")
    gpt = encode(tiny_model()[:5], vocab, "brickgpt", colorless=True)
    export_tokens.add(seqs, tiny_model()[:5], gpt, "brickgpt", -1, "g")
    seqs.save(tmp_path / "train.npz", vocab)
    return data.Split(tmp_path / "train.npz", data.Vocab.load(tmp_path / "vocab.json")), seqs.encoded


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
