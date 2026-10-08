"""Check the numpy forward pass (``brickwfc.bricks.proposal``) against the PyTorch model (``train.py``).

    python training/parity.py fixture --vocab tests/fixtures/proposal/vocab.json --out tests/fixtures/proposal
    python training/parity.py check --weights out/proposal/proposal.npz --data data/tokens

``fixture`` writes a tiny model with random weights (``proposal.npz``) and one sequence with the logits
PyTorch computes for it (``case.npz``), for ``tests/test_proposal.py``. ``check`` loads trained weights into
PyTorch and into numpy, runs validation windows through both (numpy both in one pass and token by token
through the key/value cache) and fails if the logits differ; needs ``src`` on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import MASK_PATCHES, PATCH_BITS, PREFIX, Split, Vocab, eval_windows  # noqa: E402
from train import Config, ProposalModel, export_npz  # noqa: E402


def import_npz(path: Path) -> ProposalModel:
    """A PyTorch model with the weights of an exported ``proposal.npz``."""
    import json

    with np.load(path) as data:
        w = {k: data[k] for k in data.files}
    model = ProposalModel(Config(**json.loads(str(w["config"]))))
    t = lambda a: torch.from_numpy(np.ascontiguousarray(a))  # noqa: E731
    with torch.no_grad():
        model.tok.weight.copy_(t(w["tok"]))
        model.patch.weight.copy_(t(w["patch_w"].T))
        model.patch.bias.copy_(t(w["patch_b"]))
        model.pos.weight.copy_(t(w["pos"]))
        model.ln_f.weight.copy_(t(w["ln_f_g"]))
        model.ln_f.bias.copy_(t(w["ln_f_b"]))
        for i, b in enumerate(model.blocks):
            p = f"b{i}."
            for layer, name in ((b.qkv, "qkv"), (b.proj, "proj"), (b.fc1, "fc1"), (b.fc2, "fc2")):
                layer.weight.copy_(t(w[p + name + "_w"].T))
                layer.bias.copy_(t(w[p + name + "_b"]))
            for norm, name in ((b.ln1, "ln1"), (b.ln2, "ln2")):
                norm.weight.copy_(t(w[p + name + "_g"]))
                norm.bias.copy_(t(w[p + name + "_b"]))
    return model.eval()


def fixture(vocab_path: Path, out: Path, seed: int = 0) -> None:
    vocab = Vocab.load(vocab_path)
    torch.manual_seed(seed)
    model = ProposalModel(Config(len(vocab.tokens), d_model=32, layers=2, heads=4, max_len=128)).eval()
    with torch.no_grad():  # larger than the init scale, so that every term matters in the logits
        for p in model.parameters():
            p.add_(0.1 * torch.randn_like(p))
    rng = np.random.default_rng(seed)
    head = [vocab.id("BOS"), vocab.id("SRC_set"), vocab.id("SCALE_1"), vocab.id("MASK")]
    parts = []
    for y, z, x, s, c in [(0, 1, 2, "S:brick2x4", "C:red"), (0, 3, 2, "S:plate1x2_r90", "C:white"),
                          (3, 1, 1, "S:plate2x2", "C:NONE")]:
        parts += [vocab.id(f"Y{y}"), vocab.id(f"Z{z}"), vocab.id(f"X{x}"), vocab.id(s), vocab.id(c)]
    ids = np.array(head + [vocab.id("PAD")] * MASK_PATCHES + parts, dtype=np.int64)
    patches = (rng.random((MASK_PATCHES, PATCH_BITS)) < 0.3).astype(np.float32)
    with torch.no_grad():
        logits = model(torch.from_numpy(ids)[None], torch.from_numpy(patches)[None])[0].numpy()
    out.mkdir(parents=True, exist_ok=True)
    export_npz(model, out / "proposal.npz")
    np.savez(out / "case.npz", ids=ids, patches=patches, logits=logits[PREFIX - 2 :])
    print(f"wrote {out}: logits {logits.shape}")


def check(weights: Path, data: Path, windows: int, tolerance: float) -> int:
    from brickwfc.bricks.proposal import Proposal

    model = import_npz(weights)
    numpy_model = Proposal.load(weights, weights.with_name("vocab.json"))
    vocab = Vocab.load(weights.with_name("vocab.json"))
    split = Split(data / "val.npz", vocab)
    worst = 0.0
    for ids, patches in eval_windows(split, model.config.max_len, windows)[:windows]:
        with torch.no_grad():
            expected = model(torch.from_numpy(ids)[None], torch.from_numpy(patches)[None])[0].numpy()
        full = numpy_model.forward(ids.tolist(), patches)
        cache = numpy_model.new_cache()
        numpy_model.run(cache, numpy_model.embed_prefix(ids[:4].tolist(), patches))
        stepped = np.stack([numpy_model.step(cache, [t])[-1] for t in ids[PREFIX:]])
        worst = max(worst, float(np.abs(full - expected).max()), float(np.abs(stepped - expected[PREFIX:]).max()))
    print(f"max |numpy - torch| over {windows} windows: {worst:.2e} (tolerance {tolerance:.0e})")
    if worst > tolerance:
        print("PARITY FAILED: do not use these weights with brickwfc")
        return 1
    print("parity OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fixture")
    f.add_argument("--vocab", type=Path, required=True)
    f.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("check")
    c.add_argument("--weights", type=Path, required=True)
    c.add_argument("--data", type=Path, default=Path("data/tokens"))
    c.add_argument("--windows", type=int, default=8)
    c.add_argument("--tolerance", type=float, default=2e-3)
    args = parser.parse_args(argv)
    if args.command == "fixture":
        fixture(args.vocab, args.out)
        return 0
    return check(args.weights, args.data, args.windows, args.tolerance)


if __name__ == "__main__":
    raise SystemExit(main())
