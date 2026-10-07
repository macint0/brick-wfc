"""Download models from the LDraw Official Model Repository (OMR).

    python -m brickwfc.ldraw.fetch 10013-1 10014-1 --out data/omr

Files are cached: an existing file is not downloaded again. OMR models are third-party work
(see each file's header for author and license), so they are kept out of the repository.
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path
from typing import Sequence

OMR_URL = "https://library.ldraw.org/library/omr/{set_number}.mpd"


def fetch_set(set_number: str, out_dir: Path, timeout_s: float = 60) -> Path:
    path = out_dir / f"{set_number}.mpd"
    if path.exists():
        return path
    out_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(OMR_URL.format(set_number=set_number), headers={"User-Agent": "brickwfc"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        path.write_bytes(response.read())
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.ldraw.fetch", description=__doc__.splitlines()[0])
    parser.add_argument("sets", nargs="+", help="set numbers such as 10013-1")
    parser.add_argument("--out", type=Path, default=Path("data/omr"))
    args = parser.parse_args(argv)
    for set_number in args.sets:
        path = fetch_set(set_number, args.out)
        print(f"{set_number}: {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
