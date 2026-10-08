"""Train the learned proposal model (M12b step 2) on the exported token data. Runs on Colab (T4) or CPU.

    python training/train.py --data data/tokens --out out/proposal [--d-model 256] [--steps 8000]

A small decoder-only transformer (pre-LayerNorm, causal self-attention, GELU (tanh) MLP, learned absolute
positions, output head tied to the token embedding). The target mask enters as 64 patch vectors through a
linear patch embedding at sequence positions 4..67 (``data.py`` for the layout). Next-token loss on every
position from the first part on.

Resumable: a checkpoint is written to ``--out`` at every evaluation and picked up by a rerun of the same
command. The weights with the best validation loss (with ``--val-sets``: the mean of the BrickGPT validation
loss and the loss on those held-out training sets; never the held-out fold) are exported as ``proposal.npz`` (float32 arrays in
(in, out) layout plus the config as JSON; read by ``brickwfc.bricks.proposal``), with ``vocab.json`` and
``log.jsonl`` next to them.

PyTorch is used only here (and in the notebook); it is not a dependency of the brickwfc package.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
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
    def __init__(self, c: Config) -> None:
        super().__init__()
        d = c.d_model
        self.heads = c.heads
        self.ln1, self.ln2 = nn.LayerNorm(d, eps=LN_EPS), nn.LayerNorm(d, eps=LN_EPS)
        self.qkv, self.proj = nn.Linear(d, 3 * d), nn.Linear(d, d)
        self.fc1, self.fc2 = nn.Linear(d, c.mlp * d), nn.Linear(c.mlp * d, d)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, d = x.shape
        q, k, v = self.qkv(self.ln1(x)).split(d, dim=-1)
        q, k, v = (z.view(b, t, self.heads, d // self.heads).transpose(1, 2) for z in (q, k, v))
        a = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + self.proj(a.transpose(1, 2).reshape(b, t, d))
        return x + self.fc2(F.gelu(self.fc1(self.ln2(x)), approximate="tanh"))


class ProposalModel(nn.Module):
    def __init__(self, c: Config) -> None:
        super().__init__()
        self.config = c
        self.tok = nn.Embedding(c.vocab, c.d_model)
        self.patch = nn.Linear(c.patch_bits, c.d_model)
        self.pos = nn.Embedding(c.max_len, c.d_model)
        self.blocks = nn.ModuleList(Block(c) for _ in range(c.layers))
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
        x = x + self.pos(torch.arange(ids.shape[1], device=ids.device))
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
    np.savez(path, **out)


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
    sampler = Sampler(train, args.max_len, args.set_share, args.mask_drop, exclude=excluded)

    torch.manual_seed(args.seed)
    config = Config(len(vocab.tokens), args.d_model, args.layers, args.heads, args.max_len)
    model = ProposalModel(config).to(args.device)
    decay = [p for n, p in model.named_parameters() if p.dim() == 2 and not n.startswith(("tok", "pos"))]
    other = [p for n, p in model.named_parameters() if not (p.dim() == 2 and not n.startswith(("tok", "pos")))]
    opt = torch.optim.AdamW([{"params": decay, "weight_decay": args.weight_decay}, {"params": other, "weight_decay": 0.0}],
                            lr=args.lr, betas=(0.9, 0.95))
    cuda = args.device.startswith("cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=cuda)
    params = sum(p.numel() for p in model.parameters())
    print(f"{params / 1e6:.2f}M parameters, {len(train) - len(excluded)} training builds, {len(val)} val / "
          f"{len(set_val)} set-val ({' '.join(args.val_sets) or 'none'}) / {len(heldout)} held-out windows")

    args.out.mkdir(parents=True, exist_ok=True)
    ckpt_path, log_path = args.out / "checkpoint.pt", args.out / "log.jsonl"
    step, best = 0, float("inf")
    if ckpt_path.exists():
        ckpt = torch.load(ckpt_path, map_location=args.device)
        model.load_state_dict(ckpt["model"])
        opt.load_state_dict(ckpt["opt"])
        scaler.load_state_dict(ckpt["scaler"])
        step, best = ckpt["step"], ckpt["best"]
        print(f"resumed at step {step} (best val loss {best:.4f})")
    shutil.copy(args.data / "vocab.json", args.out / "vocab.json")

    tic = time.time()
    while step < args.steps:
        rng = np.random.default_rng([args.seed, step])  # per-step generator: a resumed run draws the same batches
        ids, patches = (torch.from_numpy(a).to(args.device) for a in sampler.batch(args.batch, rng))
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
                scores["val_sets"] = args.val_sets
            # Selection never looks at the held-out sets (the test sets of the proposal comparison).
            scores["select"] = (scores["val"]["loss"] + scores["set_val"]["loss"]) / 2 if set_val else scores["val"]["loss"]
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(scores) + "\n")
            print(json.dumps(scores), flush=True)
            if scores["select"] < best:
                best = scores["select"]
                export_npz(model, args.out / "proposal.npz")
            torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "scaler": scaler.state_dict(), "step": step,
                        "best": best}, ckpt_path)
        if out_of_time:
            print(f"time limit reached at step {step}")
            break
    print(f"done: best selection loss {best:.4f}; weights in {args.out / 'proposal.npz'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
