"""M12e: training/train.py regularization (dropout, jitter) and selection (--select, the running minima in the log).
Needs PyTorch; skipped where torch does not import (it is not a dependency of the package)."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

try:
    import torch
except (ImportError, OSError):  # OSError: a broken install (a DLL that does not load)
    pytest.skip("PyTorch is not importable", allow_module_level=True)

from brickwfc.bricks.tokens import build_vocab, encode, symmetries
from brickwfc.experiments import export_tokens
from conftest import tiny_model

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "training"))
import parity  # noqa: E402
import train  # noqa: E402
from data import MASK_PATCHES, PATCH_BITS, PREFIX  # noqa: E402

CONFIG = train.Config(len(build_vocab()), d_model=32, layers=2, heads=4, max_len=128)


def batch(seed: int = 0) -> tuple[torch.Tensor, torch.Tensor]:
    rng = np.random.default_rng(seed)
    ids = torch.from_numpy(rng.integers(0, CONFIG.vocab, size=(2, PREFIX + 20)))
    patches = torch.from_numpy((rng.random((2, MASK_PATCHES, PATCH_BITS)) < 0.3).astype(np.float32))
    return ids, patches


def test_dropout_changes_training_only_and_not_the_exported_weights(tmp_path: Path) -> None:
    torch.manual_seed(0)
    plain = train.ProposalModel(CONFIG)
    torch.manual_seed(0)
    dropped = train.ProposalModel(CONFIG, dropout=0.3)
    ids, patches = batch()
    with torch.no_grad():
        assert torch.equal(plain.eval()(ids, patches), dropped.eval()(ids, patches))  # same init, eval mode
        dropped.train()
        torch.manual_seed(1)
        a = dropped(ids, patches)
        b = dropped(ids, patches)
        assert not torch.allclose(a, b)  # dropout is active in training mode
        plain.train()
        assert torch.equal(plain(ids, patches), plain(ids, patches))  # p = 0 is deterministic in training mode
    assert plain.state_dict().keys() == dropped.state_dict().keys()
    train.export_npz(plain, tmp_path / "plain.npz")
    train.export_npz(dropped, tmp_path / "dropped.npz")
    with np.load(tmp_path / "plain.npz") as p, np.load(tmp_path / "dropped.npz") as d:
        assert p.files == d.files and all(np.array_equal(p[k], d[k]) for k in p.files)  # config included
    model = parity.import_npz(tmp_path / "dropped.npz")  # numpy inference reads it as before
    with torch.no_grad():
        assert torch.allclose(model(ids, patches), dropped.eval()(ids, patches))


def tokens(out: Path) -> Path:
    """A tiny pool-style export: train (a set in 8 symmetries + BrickGPT structures), val, setval, heldout."""
    vocab = build_vocab()
    out.mkdir()
    vocab.save(out / "vocab.json")
    splits = {name: export_tokens.empty() for name in ("train", "val", "setval", "heldout")}
    for k, variant in enumerate(symmetries(tiny_model(), 8)):
        export_tokens.add(splits["train"], variant, encode(variant, vocab, "set"), "set", 0, f"t-1/sym{k}")
    for k in range(4):
        build = tiny_model()[: 6 + k]
        for name in ("train", "val"):
            export_tokens.add(splits[name], build, encode(build, vocab, "brickgpt", colorless=True), "brickgpt", -1, f"g{k}")
    for name, cut in (("setval", 12), ("heldout", 10)):
        build = tiny_model()[:cut]
        export_tokens.add(splits[name], build, encode(build, vocab, "set"), "set", 1, f"{name}-1/sym0")
    for name, seqs in splits.items():
        seqs.save(out / f"{name}.npz", vocab)
    return out


def run(data: Path, out: Path, *flags: str) -> int:
    return train.main(["--data", str(data), "--out", str(out), "--d-model", "32", "--layers", "1", "--heads", "2",
                       "--max-len", "128", "--batch", "4", "--steps", "6", "--warmup", "2", "--eval-every", "2",
                       "--set-share", "0.5", "--device", "cpu", *flags])


def log_of(out: Path) -> list[dict]:
    return [json.loads(line) for line in (out / "log.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_regularized_run_logs_both_minima_and_exports_both_selections(tmp_path: Path) -> None:
    data = tokens(tmp_path / "tokens")
    out = tmp_path / "run"
    assert run(data, out, "--dropout", "0.1", "--jitter", "set", "brickgpt", "--weight-decay", "0.3") == 0
    log = log_of(out)
    assert [row["step"] for row in log] == [2, 4, 6]
    for k, row in enumerate(log):
        seen = log[: k + 1]
        assert row["select_by"] == "mean"
        assert row["select"] == pytest.approx((row["val"]["loss"] + row["set_val"]["loss"]) / 2)
        best = min(seen, key=lambda r: r["select"])
        assert row["best"]["select"] == {"step": best["step"], "loss": best["select"]}
        set_best = min(seen, key=lambda r: r["set_val"]["loss"])
        assert row["best"]["set_val"] == {"step": set_best["step"], "loss": set_best["set_val"]["loss"]}
    assert (out / "proposal.npz").exists() and (out / "proposal_setval.npz").exists()
    # The same flags again resume the stopped run (nothing to do); another selection needs a new folder.
    assert run(data, out, "--dropout", "0.1", "--jitter", "set", "brickgpt") == 0 and len(log_of(out)) == 3
    with pytest.raises(SystemExit, match="--select mean"):
        run(data, out, "--select", "setval")


def test_select_setval_selects_on_the_real_set_loss_alone(tmp_path: Path) -> None:
    data = tokens(tmp_path / "tokens")
    out = tmp_path / "run"
    assert run(data, out, "--select", "setval", "--patience", "1") == 0
    log = log_of(out)
    assert all(row["select"] == row["set_val"]["loss"] and row["select_by"] == "setval" for row in log)
    assert log[-1]["best"]["select"] == log[-1]["best"]["set_val"]
    assert (out / "proposal.npz").exists() and not (out / "proposal_setval.npz").exists()


def test_select_setval_needs_a_set_validation_split(tmp_path: Path) -> None:
    data = tokens(tmp_path / "tokens")
    (data / "setval.npz").unlink()
    with pytest.raises(SystemExit):
        run(data, tmp_path / "run", "--select", "setval")
