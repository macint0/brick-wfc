"""Train the learned proposal model (M12b step 2) on the exported token data. Runs on Colab (T4) or CPU.

    python training/train.py --data data/tokens --out out/proposal [--d-model 256] [--steps 8000]

A small decoder-only transformer (pre-LayerNorm, causal self-attention, GELU (tanh) MLP, learned absolute
positions, output head tied to the token embedding). The target mask enters as 64 patch vectors through a
linear patch embedding at sequence positions 4..67 (``data.py`` for the layout). Next-token loss on every
position from the first part on.

Resumable: a checkpoint is written to ``--out`` at every evaluation and picked up by a rerun of the same
command. The weights with the best validation loss (with ``--val-sets``, or a ``setval.npz`` in ``--data`` (M12e
pool exports): the mean of the BrickGPT validation loss and the real-set validation loss; never the held-out
sets) are exported as ``proposal.npz`` (float32 arrays in
(in, out) layout plus the config as JSON; read by ``brickwfc.bricks.proposal``), with ``vocab.json`` and
``log.jsonl`` next to them. ``--patience N`` stops after N evaluations in a row without a new best selection loss.
``--select setval`` selects on the real-set validation loss alone. Every log line records the running minima of the
selection loss and of the set validation loss with their steps (``best``), and the weights at the set validation
minimum are also exported as ``proposal_setval.npz`` (same format).

Regularization (M12e; all off by default, so a default run is unchanged): ``--dropout p`` on the embeddings, the
attention weights and both residual branches (training mode only; nothing changes in the exported weights or at
inference), ``--jitter set [brickgpt]`` moves training windows by a random Z / X shift (``data.py``), and
``--weight-decay``.

PyTorch is used only here (and in the notebook); it is not a dependency of the brickwfc package.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import (MASK_PATCHES, PART_TOKENS, PATCH_BITS, PREFIX, Sampler, Split, Vocab, collate, eval_windows,  # noqa: E402
                  set_builds)

FIELDS = ("Y", "Z", "X", "shape", "color")
LN_EPS = 1e-5


@dataclass
class Config:
    vocab: int
    d_model: int = 256
    layers: int = 6
    heads: int = 8
    max_len: int = 1024
    mlp: int = 4  # hidden width / d_model
    patch_bits: int = PATCH_BITS
    prefix: int = PREFIX


class Block(nn.Module):
    def __init__(self, c: Config, dropout: float = 0.0) -> None:
        super().__init__()
        d = c.d_model
        self.heads, self.dropout = c.heads, dropout
        self.ln1, self.ln2 = nn.LayerNorm(d, eps=LN_EPS), nn.LayerNorm(d, eps=LN_EPS)
        self.qkv, self.proj = nn.Linear(d, 3 * d), nn.Linear(d, d)
        self.fc1, self.fc2 = nn.Linear(d, c.mlp * d), nn.Linear(c.mlp * d, d)
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, d = x.shape
        q, k, v = self.qkv(self.ln1(x)).split(d, dim=-1)
        q, k, v = (z.view(b, t, self.heads, d // self.heads).transpose(1, 2) for z in (q, k, v))
        a = F.scaled_dot_product_attention(q, k, v, is_causal=True, dropout_p=self.dropout if self.training else 0.0)
        x = x + self.drop(self.proj(a.transpose(1, 2).reshape(b, t, d)))
        return x + self.drop(self.fc2(F.gelu(self.fc1(self.ln2(x)), approximate="tanh")))


class ProposalModel(nn.Module):
    def __init__(self, c: Config, dropout: float = 0.0) -> None:
        """``dropout``: on the input embeddings, the attention weights and both residual branches, in training
        mode only. It is not part of ``Config`` (nor of ``proposal.npz``): it has no parameters, and inference
        (eval mode, numpy) is the same model without it."""
        super().__init__()
        self.config = c
        self.tok = nn.Embedding(c.vocab, c.d_model)
        self.patch = nn.Linear(c.patch_bits, c.d_model)
        self.pos = nn.Embedding(c.max_len, c.d_model)
        self.drop = nn.Dropout(dropout)
        self.blocks = nn.ModuleList(Block(c, dropout) for _ in range(c.layers))
        self.ln_f = nn.LayerNorm(c.d_model, eps=LN_EPS)
        self.apply(self._init)
        for block in self.blocks:  # scaled init of the residual projections (GPT-2)
            for layer in (block.proj, block.fc2):
                nn.init.normal_(layer.weight, std=0.02 / math.sqrt(2 * c.layers))

    @staticmethod
    def _init(module: nn.Module) -> None:
        if isinstance(module, (nn.Linear, nn.Embedding)):
            nn.init.normal_(module.weight, std=0.02)
        if isinstance(module, nn.Linear) and module.bias is not None:
            nn.init.zeros_(module.bias)

    def forward(self, ids: torch.Tensor, patches: torch.Tensor) -> torch.Tensor:
        """Logits (B, L, V) for ids (B, L) and patches (B, 64, 125); ids in the mask slots are ignored."""
        x = self.tok(ids)
        x = torch.cat([x[:, :4], self.patch(patches), x[:, PREFIX:]], dim=1)
        x = self.drop(x + self.pos(torch.arange(ids.shape[1], device=ids.device)))
        for block in self.blocks:
            x = block(x)
        return self.ln_f(x) @ self.tok.weight.T


def loss_terms(model: ProposalModel, ids: torch.Tensor, patches: torch.Tensor, pad: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """(per-target losses, valid mask, field index) for the targets from position PREFIX on."""
    logits = model(ids, patches)[:, PREFIX - 1 : -1]
    targets = ids[:, PREFIX:]
    losses = F.cross_entropy(logits.reshape(-1, logits.shape[-1]).float(), targets.reshape(-1), reduction="none")
    field = (torch.arange(targets.shape[1], device=ids.device) % PART_TOKENS).expand_as(targets)
    return losses.view_as(targets), targets != pad, field


# Export ---------------------------------------------------------------------------------------------------


def export_npz(model: ProposalModel, path: Path) -> None:
    """Weights as float32 arrays, linear layers in (in, out) layout, plus the config."""
    arrays = {"tok": model.tok.weight, "patch_w": model.patch.weight.T, "patch_b": model.patch.bias,
              "pos": model.pos.weight, "ln_f_g": model.ln_f.weight, "ln_f_b": model.ln_f.bias}
    for i, b in enumerate(model.blocks):
        arrays.update({f"b{i}.ln1_g": b.ln1.weight, f"b{i}.ln1_b": b.ln1.bias, f"b{i}.ln2_g": b.ln2.weight,
                       f"b{i}.ln2_b": b.ln2.bias, f"b{i}.qkv_w": b.qkv.weight.T, f"b{i}.qkv_b": b.qkv.bias,
                       f"b{i}.proj_w": b.proj.weight.T, f"b{i}.proj_b": b.proj.bias, f"b{i}.fc1_w": b.fc1.weight.T,
                       f"b{i}.fc1_b": b.fc1.bias, f"b{i}.fc2_w": b.fc2.weight.T, f"b{i}.fc2_b": b.fc2.bias})
    out = {k: v.detach().float().cpu().numpy().copy() for k, v in arrays.items()}
    out["config"] = np.array(json.dumps(asdict(model.config)))
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez(tmp, **out)
    tmp.replace(path)


# Training -------------------------------------------------------------------------------------------------


@torch.no_grad()
def evaluate(model: ProposalModel, windows: list, pad: int, device: str, batch: int) -> dict[str, float]:
    """Mean loss per target token, overall and per field."""
    model.eval()
    sums, counts = np.zeros(PART_TOKENS), np.zeros(PART_TOKENS)
    for i in range(0, len(windows), batch):
        ids, patches = collate(windows[i : i + batch], pad)
        losses, valid, field = loss_terms(model, torch.from_numpy(ids).to(device), torch.from_numpy(patches).to(device), pad)
        for f in range(PART_TOKENS):
            m = valid & (field == f)
            sums[f] += losses[m].sum().item()
            counts[f] += m.sum().item()
    model.train()
    out = {name: float(sums[f] / max(counts[f], 1)) for f, name in enumerate(FIELDS)}
    out["loss"] = float(sums.sum() / max(counts.sum(), 1))
    return out


def lr_at(step: int, steps: int, peak: float, warmup: int) -> float:
    if step < warmup:
        return peak * (step + 1) / warmup
    progress = min(1.0, (step - warmup) / max(1, steps - warmup))
    return peak * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * progress)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data/tokens"))
    parser.add_argument("--out", type=Path, default=Path("out/proposal"))
    parser.add_argument("--d-model", type=int, default=256)
    parser.add_argument("--layers", type=int, default=6)
    parser.add_argument("--heads", type=int, default=8)
    parser.add_argument("--max-len", type=int, default=1024)
    parser.add_argument("--steps", type=int, default=8000)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--warmup", type=int, default=300)
    parser.add_argument("--weight-decay", type=float, default=0.1)
    parser.add_argument("--set-share", type=float, default=0.25, help="share of training windows from real sets")
    parser.add_argument("--mask-drop", type=float, default=0.2, help="share of windows trained without a target")
    parser.add_argument("--eval-every", type=int, default=500)
    parser.add_argument("--val-builds", type=int, default=400, help="BrickGPT test structures in the validation loss")
    parser.add_argument("--minutes", type=float, default=0, help="stop (and export) after this long; 0 = no limit")
    parser.add_argument("--val-sets", nargs="*", default=[],
                        help="training sets held out of training (all their symmetries) as set validation; with them, "
                             "the weights are selected on the mean of the BrickGPT and set validation losses")
    parser.add_argument("--patience", type=int, default=0,
                        help="stop after this many evaluations without a new best selection loss; 0 = never")
    parser.add_argument("--select", choices=("mean", "setval"), default="mean",
                        help="selection loss: the mean of the BrickGPT and set validation losses (default), or the set "
                             "validation loss alone")
    parser.add_argument("--dropout", type=float, default=0.0,
                        help="dropout on embeddings, attention and residual branches (training only; 0 = none)")
    parser.add_argument("--jitter", nargs="*", choices=("brickgpt", "set"), default=[],
                        help="sources whose training windows are moved by a random Z / X shift (data.py)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args(argv)

    started = time.time()
    vocab = Vocab.load(args.data / "vocab.json")
    pad = vocab.id("PAD")
    train = Split(args.data / "train.npz", vocab)
    val = eval_windows(Split(args.data / "val.npz", vocab), args.max_len, args.val_builds)
    heldout = eval_windows(Split(args.data / "heldout.npz", vocab), args.max_len)
    # Every symmetry of the validation sets is held out of training, so all of them are validation windows.
    excluded = set_builds(train, args.val_sets)[0] if args.val_sets else []
    set_val = eval_windows(train, args.max_len, indices=excluded)
    if not args.val_sets and (args.data / "setval.npz").exists():  # a pool export's real-set validation split
        set_val = eval_windows(Split(args.data / "setval.npz", vocab), args.max_len)
    if args.select == "setval" and not set_val:
        parser.error("--select setval needs --val-sets or a setval.npz in --data")
    sampler = Sampler(train, args.max_len, args.set_share, args.mask_drop, exclude=excluded, jitter=args.jitter)

    torch.manual_seed(args.seed)
    config = Config(len(vocab.tokens), args.d_model, args.layers, args.heads, args.max_len)
    model = ProposalModel(config, args.dropout).to(args.device)
    decay = [p for n, p in model.named_parameters() if p.dim() == 2 and not n.startswith(("tok", "pos"))]
    other = [p for n, p in model.named_parameters() if not (p.dim() == 2 and not n.startswith(("tok", "pos")))]
    opt = torch.optim.AdamW([{"params": decay, "weight_decay": args.weight_decay}, {"params": other, "weight_decay": 0.0}],
                            lr=args.lr, betas=(0.9, 0.95))
    cuda = args.device.startswith("cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=cuda)
    params = sum(p.numel() for p in model.parameters())
    print(f"{params / 1e6:.2f}M parameters, {len(train) - len(excluded)} training builds, {len(val)} val / "
          f"{len(set_val)} set-val ({' '.join(args.val_sets) or ('setval.npz' if set_val else 'none')}) / {len(heldout)} held-out windows")
    print(f"selection {args.select}, dropout {args.dropout}, jitter {' '.join(args.jitter) or 'none'}, "
          f"weight decay {args.weight_decay}, set share {args.set_share}")

    args.out.mkdir(parents=True, exist_ok=True)
    ckpt_path, log_path = args.out / "checkpoint.pt", args.out / "log.jsonl"
    step, best, stale = 0, float("inf"), 0
    # Running minima, recorded in every log line: the selection loss and the set validation loss (with their steps).
    best_step, set_best, set_best_step = None, float("inf"), None
    if ckpt_path.exists():
        ckpt = torch.load(ckpt_path, map_location=args.device)
        if ckpt.get("select", "mean") != args.select:
            raise SystemExit(f"{ckpt_path} was trained with --select {ckpt.get('select', 'mean')}; use a new --out")
        model.load_state_dict(ckpt["model"])
        opt.load_state_dict(ckpt["opt"])
        scaler.load_state_dict(ckpt["scaler"])
        step, best, stale = ckpt["step"], ckpt["best"], ckpt.get("stale", 0)
        best_step, set_best, set_best_step = ckpt.get("best_step"), ckpt.get("set_best", float("inf")), ckpt.get("set_best_step")
        print(f"resumed at step {step} (best selection loss {best:.4f}, {stale} evaluations without improvement)")
        if args.patience and stale >= args.patience:
            print("already stopped early; nothing to do")
            return 0
    shutil.copy(args.data / "vocab.json", args.out / "vocab.json")

    def draw(at: int) -> tuple[np.ndarray, np.ndarray]:
        # Per-step generator: a resumed run draws the same batches, with or without the prefetch below.
        return sampler.batch(args.batch, np.random.default_rng([args.seed, at]))

    # The next batch is sampled on a thread while the GPU works on this one (sampling is CPU-bound).
    prefetch = ThreadPoolExecutor(max_workers=1)
    pending = prefetch.submit(draw, step)
    tic = time.time()
    while step < args.steps:
        batch = pending.result()
        pending = prefetch.submit(draw, step + 1)
        ids, patches = (torch.from_numpy(a).to(args.device) for a in batch)
        for group in opt.param_groups:
            group["lr"] = lr_at(step, args.steps, args.lr, args.warmup)
        with torch.autocast("cuda", dtype=torch.float16, enabled=cuda):
            losses, valid, _ = loss_terms(model, ids, patches, pad)
            loss = losses[valid].mean()
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        step += 1
        out_of_time = args.minutes > 0 and time.time() - started > 60 * args.minutes
        if step % 50 == 0:
            print(f"step {step} loss {loss.item():.4f} lr {opt.param_groups[0]['lr']:.2e} {(time.time() - tic) / 50:.3f}s/step",
                  flush=True)
            tic = time.time()
        if step % args.eval_every == 0 or step == args.steps or out_of_time:
            scores = {"step": step, "train_loss": loss.item(), "val": evaluate(model, val, pad, args.device, args.batch),
                      "heldout_sets": evaluate(model, heldout, pad, args.device, args.batch), "minutes": (time.time() - started) / 60}
            if set_val:
                scores["set_val"] = evaluate(model, set_val, pad, args.device, args.batch)
                scores["val_sets"] = args.val_sets or "setval.npz"
            # Selection never looks at the held-out sets (the test sets of the proposal comparison).
            if args.select == "setval":
                scores["select"] = scores["set_val"]["loss"]
            else:
                scores["select"] = (scores["val"]["loss"] + scores["set_val"]["loss"]) / 2 if set_val else scores["val"]["loss"]
            scores["select_by"] = args.select
            improved = scores["select"] < best
            if improved:
                best, best_step, stale = scores["select"], step, 0
            else:
                stale += 1
            set_improved = bool(set_val) and scores["set_val"]["loss"] < set_best
            if set_improved:
                set_best, set_best_step = scores["set_val"]["loss"], step
            scores["best"] = {"select": {"step": best_step, "loss": best}}
            if set_val:
                scores["best"]["set_val"] = {"step": set_best_step, "loss": set_best}
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(scores) + "\n")
            print(json.dumps(scores), flush=True)
            if improved:
                export_npz(model, args.out / "proposal.npz")
            if set_improved and args.select != "setval":  # the weights a --select setval run would have chosen
                export_npz(model, args.out / "proposal_setval.npz")
            # Written next to the old checkpoint, then swapped in: a disconnect mid-write keeps the last good one.
            torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "scaler": scaler.state_dict(), "step": step,
                        "best": best, "stale": stale, "best_step": best_step, "set_best": set_best,
                        "set_best_step": set_best_step, "select": args.select}, ckpt_path.with_suffix(".tmp"))
            ckpt_path.with_suffix(".tmp").replace(ckpt_path)
            if args.patience and stale >= args.patience:
                print(f"early stop at step {step}: {stale} evaluations without a new best (best {best:.4f})")
                break
        if out_of_time:
            print(f"time limit reached at step {step}")
            break
    prefetch.shutdown(cancel_futures=True)
    print(f"done: best selection loss {best:.4f} at step {best_step}; weights in {args.out / 'proposal.npz'}")
    if set_val and args.select != "setval":
        print(f"set validation minimum {set_best:.4f} at step {set_best_step}; weights in {args.out / 'proposal_setval.npz'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
