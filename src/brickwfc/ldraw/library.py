"""Read LDraw library part files and measure the facts the catalog's placement test checks (M12d).

    python -m brickwfc.ldraw.library 3659 3455 --cache data/ldraw

A part file is resolved through its subfiles (``s/`` subparts, ``p/`` and ``p/48/`` primitives), read from
``--cache`` (gitignored, like the OMR models) and fetched from the official library into it when missing. The
library rate-limits single files; to measure many parts, unpack its ``parts/`` and ``p/`` folders from
https://library.ldraw.org/library/updates/complete.zip into the cache first (lower-case paths). For each part it reports, in LDU
from the part's origin (LDraw axes, -Y up):

- the top studs (stud primitives facing up) and the side studs (facing sideways, with their direction);
- the body's extent along x, z and y, studs left out;
- for each 20 x 20 LDU cell of the body's footprint, how much of it the bottom plane (the faces at the body's
  lowest y) covers: a cell the bottom plane touches can rest on a stud below ("seated").

The output is the ``LDRAW`` fact table of ``tests/test_catalog_shapes.py``; the test itself never fetches.
"""

from __future__ import annotations

import argparse
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

LIBRARY_URL = "https://library.ldraw.org/library/official/{path}"
CELL_LDU = 20
# Stud primitives that face away from the part (a stud something clicks onto). The others (stud3, stud4, ...)
# are the tubes and holders on a part's underside and count as body.
STUD = re.compile(r"^stud(2a?|6a?|7a?|10|13|15|17a|20|22a|28)?\.dat$")
UNDERSIDE = re.compile(r"^stud(3a?|4[a-z]*|12|16|18a?|24)\.dat$")
MAX_DEPTH = 32

Loader = Callable[[str], str]


def library_paths(name: str) -> list[str]:
    """Where a subfile reference lives in the library: ``s\\x.dat`` under parts/, ``48\\x.dat`` under p/, a
    bare name under parts/ or else p/."""
    name = name.strip().replace("\\", "/").lower()
    if name.startswith("s/"):
        return [f"parts/{name}"]
    if name.startswith(("48/", "8/")):
        return [f"p/{name}"]
    return [f"parts/{name}", f"p/{name}"]


def _download(url: str, timeout_s: float, pause_s: float, retries: int = 6) -> str | None:
    """The file at ``url``, or None if the library does not have it (404). Waits ``pause_s`` before each request
    and backs off when the server asks to slow down (429, 503)."""
    wait = pause_s
    for _ in range(retries):
        time.sleep(wait)
        request = urllib.request.Request(url, headers={"User-Agent": "brickwfc"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in (429, 503):
                raise
            retry_after = error.headers.get("Retry-After", "")
            wait = max(2 * wait, float(retry_after) if retry_after.isdigit() else 5.0)
    raise OSError(f"{url}: still rate-limited after {retries} tries")


def cached_loader(cache: Path, fetch: bool = True, timeout_s: float = 30, pause_s: float = 0.5) -> Loader:
    """A loader that reads ``cache/<library path>`` and, with ``fetch``, downloads missing files into it (one
    request per ``pause_s``). Returns "" for a file the library does not have."""

    def load(name: str) -> str:
        paths = library_paths(name)
        for path in paths:
            file = cache / path
            if file.exists():
                return file.read_text(encoding="utf-8", errors="replace")
        if not fetch:
            return ""
        for path in paths:
            text = _download(LIBRARY_URL.format(path=path), timeout_s, pause_s)
            if text is None:
                continue
            file = cache / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
            return text
        return ""

    return load


@dataclass(frozen=True)
class StudRef:
    file: str
    position: tuple[float, float, float]
    up: tuple[float, float, float]  # the direction the stud points (LDraw: -Y is up)


@dataclass
class Resolved:
    """Every vertex and face of a part with its subfiles expanded, and its outward stud primitives."""

    points: list[np.ndarray] = field(default_factory=list)
    faces: list[np.ndarray] = field(default_factory=list)  # (3, 3) or (4, 3) vertex arrays
    studs: list[StudRef] = field(default_factory=list)
    missing: set[str] = field(default_factory=set)
    title: str = ""


def resolve(name: str, load: Loader) -> Resolved:
    out = Resolved()

    def walk(file: str, rotation: np.ndarray, origin: np.ndarray, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise ValueError(f"subfile nesting deeper than {MAX_DEPTH} at {file!r}")
        text = load(file)
        if not text.strip():
            out.missing.add(file)
            return
        if depth == 0:
            out.title = next((line[2:].strip() for line in text.splitlines() if line.strip()), "")
        for line in text.splitlines():
            tokens = line.split()
            if not tokens or tokens[0] not in "12345" or len(tokens[0]) != 1:
                continue
            if tokens[0] == "1":
                values = [float(t) for t in tokens[2:14]]
                sub = " ".join(tokens[14:]).lower()
                sub_origin = origin + rotation @ np.array(values[:3])
                sub_rotation = rotation @ np.array(values[3:]).reshape(3, 3)
                base = sub.replace("\\", "/").split("/")[-1]
                if STUD.match(base):
                    up = -sub_rotation[:, 1]  # a stud primitive rises along its local -Y
                    out.studs.append(StudRef(base, tuple(np.round(sub_origin, 3) + 0.0), tuple(np.round(up / np.linalg.norm(up), 3) + 0.0)))
                    continue
                walk(sub, sub_rotation, sub_origin, depth + 1)
            elif tokens[0] in "34":
                count = int(tokens[0])
                vertices = np.array([float(t) for t in tokens[2:2 + 3 * count]]).reshape(count, 3)
                world = (rotation @ vertices.T).T + origin
                out.faces.append(world)
                out.points.extend(world)
            else:  # lines and optional lines: their two end points
                vertices = np.array([float(t) for t in tokens[2:8]]).reshape(2, 3)
                out.points.extend((rotation @ vertices.T).T + origin)

    walk(name if name.endswith(".dat") else f"{name}.dat", np.eye(3), np.zeros(3), 0)
    return out


@dataclass(frozen=True)
class PartFacts:
    file: str
    title: str
    top_studs: list[tuple[float, float]]  # (x, z)
    top_stud_y: list[float]
    side_studs: list[tuple[tuple[float, float, float], tuple[float, float, float]]]  # (position, direction)
    x: tuple[float, float]
    z: tuple[float, float]
    y: tuple[float, float]  # (top, bottom): -Y is up
    bottom_cover: dict[tuple[float, float], float]  # cell centre (x, z) -> share of the cell the bottom plane covers
    missing: tuple[str, ...]


def _inside(face: np.ndarray, px: np.ndarray, pz: np.ndarray) -> np.ndarray:
    """Which (px, pz) points lie in the xz projection of a triangle or (convex) quad."""
    triangles = [face[[0, 1, 2]]] + ([face[[0, 2, 3]]] if len(face) == 4 else [])
    hit = np.zeros(px.shape, dtype=bool)
    for a, b, c in ([t[i][[0, 2]] for i in range(3)] for t in triangles):
        def side(p: np.ndarray, q: np.ndarray) -> np.ndarray:
            return (q[0] - p[0]) * (pz - p[1]) - (q[1] - p[1]) * (px - p[0])

        s1, s2, s3 = side(a, b), side(b, c), side(c, a)
        hit |= ((s1 >= 0) & (s2 >= 0) & (s3 >= 0)) | ((s1 <= 0) & (s2 <= 0) & (s3 <= 0))
    return hit


def facts(name: str, load: Loader) -> PartFacts:
    part = resolve(name, load)
    points = np.array(part.points)
    lo, hi = points.min(axis=0), points.max(axis=0)
    bottom = [f for f in part.faces if np.allclose(f[:, 1], hi[1], atol=1e-3)]
    cover: dict[tuple[float, float], float] = {}
    steps = np.arange(0.5, CELL_LDU, 1.0)
    for x0 in np.arange(lo[0], hi[0] - 1e-6, CELL_LDU):
        for z0 in np.arange(lo[2], hi[2] - 1e-6, CELL_LDU):
            px, pz = np.meshgrid(x0 + steps, z0 + steps)
            hit = np.zeros(px.shape, dtype=bool)
            for face in bottom:
                hit |= _inside(face, px, pz)
            cover[(float(x0 + CELL_LDU / 2), float(z0 + CELL_LDU / 2))] = round(float(hit.mean()), 3)
    top = [s for s in part.studs if np.allclose(s.up, (0, -1, 0), atol=1e-3)]
    side = [(s.position, s.up) for s in part.studs if abs(s.up[1]) < 1e-3]
    return PartFacts(
        name, part.title, [(s.position[0], s.position[2]) for s in top], sorted({s.position[1] for s in top}), side,
        (float(lo[0]), float(hi[0])), (float(lo[2]), float(hi[2])), (float(lo[1]), float(hi[1])), cover,
        tuple(sorted(part.missing)),
    )


def _num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def cell_map(f: PartFacts) -> list[str]:
    """One text row per cell row of the footprint (z ascending), one character per cell (x ascending): ``S`` a top
    stud on a flat-bottomed cell, ``s`` a stud on a cell the bottom plane does not touch, ``#`` flat bottom without
    a stud, ``.`` neither."""
    studs = {(round(x), round(z)) for x, z in f.top_studs}
    xs = sorted({x for x, _ in f.bottom_cover})
    zs = sorted({z for _, z in f.bottom_cover})
    rows = []
    for z in zs:
        row = ""
        for x in xs:
            stud, flat = (round(x), round(z)) in studs, f.bottom_cover[(x, z)] > 0
            row += "S" if stud and flat else "s" if stud else "#" if flat else "."
        rows.append(row)
    return rows


def describe(f: PartFacts) -> str:
    """A compact report: extents, the cell map (``cell_map``), studs that are off the cell centres, side studs."""
    centres = {(round(x), round(z)) for x, z in f.bottom_cover}
    off = [(x, z) for x, z in f.top_studs if (round(x), round(z)) not in centres]
    lines = [f"== {f.file}: {f.title}",
             f"  x ({_num(f.x[0])}, {_num(f.x[1])})  z ({_num(f.z[0])}, {_num(f.z[1])})  y ({_num(f.y[0])}, {_num(f.y[1])})"
             f"  studs {len(f.top_studs)} at y {[_num(y) for y in f.top_stud_y]}"]
    lines += [f"  | {row}" for row in cell_map(f)]
    if off:
        lines.append("  studs off the cell centres: " + ", ".join(f"({_num(x)}, {_num(z)})" for x, z in off))
    if f.side_studs:
        lines.append("  side studs " + ", ".join(f"{tuple(_num(v) for v in p)} -> {tuple(_num(v) for v in d)}"
                                               for p, d in f.side_studs))
    thin = sorted(share for share in f.bottom_cover.values() if 0 < share < 0.1)
    if thin:
        lines.append(f"  {len(thin)} cells with under 10% bottom cover (min {thin[0]:.2f})")
    if f.missing:
        lines.append(f"  MISSING subfiles: {', '.join(f.missing)}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m brickwfc.ldraw.library", description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="+", help="part file names such as 3659 or 3659.dat")
    parser.add_argument("--cache", type=Path, default=Path("data/ldraw"))
    parser.add_argument("--offline", action="store_true", help="read the cache only")
    args = parser.parse_args(argv)
    load = cached_loader(args.cache, fetch=not args.offline)
    for name in args.parts:
        print(describe(facts(name, load)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
