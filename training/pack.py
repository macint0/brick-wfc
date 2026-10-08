"""Pack everything the Colab notebook needs into one zip (the repository is private, so Colab does not clone it).

    python training/pack.py --data data/tokens --out out/colab/brick_proposal.zip

Contents: ``data/tokens/*`` (from ``experiments/export_tokens.py``), ``training/*.py`` and ``src/brickwfc``
(Python files only, for the numpy parity check). Upload the zip in ``training/train.ipynb``.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pack(data: Path, out: Path) -> list[str]:
    files = [(p, Path("data/tokens") / p.name) for p in sorted(data.glob("*")) if p.suffix in (".npz", ".json")]
    files += [(p, p.relative_to(ROOT)) for p in sorted((ROOT / "training").glob("*.py"))]
    files += [(p, p.relative_to(ROOT)) for p in sorted((ROOT / "src" / "brickwfc").rglob("*.py"))]
    names = {str(arc) for _, arc in files}
    for required in ("data/tokens/train.npz", "data/tokens/val.npz", "data/tokens/heldout.npz", "data/tokens/vocab.json"):
        if required not in {n.replace("\\", "/") for n in names}:
            raise SystemExit(f"missing {required}: run python -m brickwfc.experiments.export_tokens first")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, arc in files:
            z.write(path, arc.as_posix())
    return [arc.as_posix() for _, arc in files]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "tokens")
    parser.add_argument("--out", type=Path, default=ROOT / "out" / "colab" / "brick_proposal.zip")
    args = parser.parse_args(argv)
    names = pack(args.data, args.out)
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB, {len(names)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
