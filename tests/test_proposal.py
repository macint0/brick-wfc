"""M12b step 2: numpy inference of the proposal model (parity with PyTorch, key/value cache, sessions, speed)."""

import json
import time
from pathlib import Path

import numpy as np
import pytest

from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.parts import CATALOG, Shape
from brickwfc.bricks.proposal import Proposal
from brickwfc.bricks.tokens import MASK_PATCHES, PATCH_BITS, PREFIX, Vocab, build_vocab, ordered, part_tokens
from conftest import tiny_model

FIXTURE = Path(__file__).parent / "fixtures" / "proposal"


def random_proposal(d: int = 32, layers: int = 2, heads: int = 4, max_len: int = 128, seed: int = 0) -> Proposal:
    """A model with random weights in the exported layout."""
    vocab = build_vocab()
    rng = np.random.default_rng(seed)
    r = lambda *shape: (0.1 * rng.standard_normal(shape)).astype(np.float32)  # noqa: E731
    w = {"tok": r(len(vocab), d), "patch_w": r(PATCH_BITS, d), "patch_b": r(d), "pos": r(max_len, d),
         "ln_f_g": 1 + r(d), "ln_f_b": r(d)}
    for i in range(layers):
        w.update({f"b{i}.ln1_g": 1 + r(d), f"b{i}.ln1_b": r(d), f"b{i}.ln2_g": 1 + r(d), f"b{i}.ln2_b": r(d),
                  f"b{i}.qkv_w": r(d, 3 * d), f"b{i}.qkv_b": r(3 * d), f"b{i}.proj_w": r(d, d), f"b{i}.proj_b": r(d),
                  f"b{i}.fc1_w": r(d, 4 * d), f"b{i}.fc1_b": r(4 * d), f"b{i}.fc2_w": r(4 * d, d), f"b{i}.fc2_b": r(d)})
    w["config"] = np.array(json.dumps({"vocab": len(vocab), "d_model": d, "layers": layers, "heads": heads,
                                       "max_len": max_len, "mlp": 4, "patch_bits": PATCH_BITS, "prefix": PREFIX}))
    return Proposal(w, vocab)


def test_numpy_forward_matches_pytorch_fixture() -> None:
    model = Proposal.load(FIXTURE / "proposal.npz", FIXTURE / "vocab.json")
    with np.load(FIXTURE / "case.npz") as case:
        ids, patches, expected = case["ids"], case["patches"], case["logits"]
    logits = model.forward(ids.tolist(), patches)
    np.testing.assert_allclose(logits[PREFIX - 2 :], expected, atol=1e-4, rtol=1e-4)


def test_fixture_vocab_is_the_current_vocab() -> None:
    # The fixture was made with this vocabulary; if the catalog or palette changes, regenerate it
    # (training/parity.py fixture) together with the vocabulary file.
    assert Vocab.load(FIXTURE / "vocab.json") == build_vocab()


def test_cached_steps_equal_one_full_pass() -> None:
    model = random_proposal(max_len=256)
    vocab = model.vocab
    ids = [vocab.id("BOS"), vocab.id("SRC_set"), vocab.id("SCALE_1"), vocab.id("MASK")] + [0] * MASK_PATCHES
    ids += [t for p in ordered(tiny_model()) for t in part_tokens(p, vocab)]
    patches = (np.random.default_rng(1).random((MASK_PATCHES, PATCH_BITS)) < 0.5).astype(np.float32)
    full = model.forward(ids, patches)
    cache = model.new_cache()
    model.run(cache, model.embed_prefix(ids[:4], patches))
    chunks = [model.step(cache, ids[i : i + 3]) for i in range(PREFIX, len(ids), 3)]
    np.testing.assert_allclose(np.concatenate(chunks), full[PREFIX:], atol=1e-4)


def test_session_queries_roll_back_and_windows_slide() -> None:
    model = random_proposal(max_len=PREFIX + 5 * 6 + 1)  # 6 parts per window
    shapes = [Shape(CATALOG["brick2x4"], False), Shape(CATALOG["plate1x2"], True), Shape(CATALOG["brick1x1_3062a"], False)]
    colors = colors_by_name(["red", "white", "red"])
    shapes, colors = model.choice_tokens(list(zip(shapes, colors)))
    assert shapes[2] >= 0 and colors[1] == model.vocab.id("C:white")
    assert model.choice_tokens([(Shape(CATALOG["brick2x4"], True), colors_by_name(["red"])[0])])[0][0] >= 0
    session = model.session((12, 10, 10), allowed=None)
    first = session.weights(0, 0, 0, shapes, colors)
    assert first.shape == (3,) and (first > 0).all()
    assert np.allclose(session.weights(0, 0, 0, shapes, colors), first)  # the query left no trace
    for part in ordered(tiny_model()):  # 16 parts: the window slides twice
        session.add(part)
    assert len(session.rows) == len(tiny_model()) and session.first > 0
    assert session.cache.length <= model.max_len
    assert np.allclose(session.weights(6, 2, 2, shapes, colors), session.weights(6, 2, 2, shapes, colors))
    assert (session.weights(500, 0, 0, shapes, colors) == 1).all()  # outside the token grid: neutral
    target = np.zeros((12, 10, 10), dtype=bool)
    target[:, :4, :4] = True
    assert not np.allclose(model.session((12, 10, 10), target).weights(0, 0, 0, shapes, colors), first)


def test_one_step_at_length_300_is_fast() -> None:
    model = random_proposal(d=256, layers=6, heads=8, max_len=1024)
    cache = model.new_cache()
    model.run(cache, np.zeros((300, 256), np.float32))
    times = []
    for _ in range(7):
        cache.length = 300
        tic = time.perf_counter()
        model.step(cache, [5])
        times.append(time.perf_counter() - tic)
    assert min(times) < 0.05, f"one step took {1000 * min(times):.1f} ms"
