"""Tip-over check (M12): does every cluster of parts stay upright on a table?

In the physics model (``physics.py``) clutch is pull-only per stud ring but unbounded when we only ask
whether *some* clutch suffices, and a stud contact then passes any vertical force and any tilting moment.
So parts joined through stud contacts act as one rigid body, a *cluster*, and only the table is
push-only. A cluster stands iff its centre of mass (one weight unit per cell, at each part's footprint
centre) lies in the convex hull of its ground contacts (the corners of its layer-0 cells). The build
needs finite clutch (``physics.required_clutch < inf``) iff every cluster stands; how much clutch it
needs (cantilevers) is a separate question.

``Balance`` tracks clusters while parts are placed bottom-up (union-find over parts, with mass, moment
and hull per cluster), so a builder can refuse a part that would tip its cluster over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from brickwfc.bricks.parts import PlacedPart

Point = tuple[float, float]  # (x, z) in stud units
TOLERANCE = 1e-9


def convex_hull(points: Iterable[Point]) -> list[Point]:
    """Counter-clockwise hull vertices (Andrew's monotone chain); collinear points are dropped."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def outside_distance(point: Point, hull: Sequence[Point]) -> float:
    """How far ``point`` lies outside the convex polygon ``hull`` (counter-clockwise, >= 3 vertices):
    the largest distance past any edge's line; <= 0 inside."""
    worst = -float("inf")
    for (ax, az), (bx, bz) in zip(hull, list(hull[1:]) + [hull[0]]):
        length = ((bx - ax) ** 2 + (bz - az) ** 2) ** 0.5
        # Positive to the right of edge a -> b, i.e. outside a counter-clockwise polygon.
        worst = max(worst, ((bx - ax) * (az - point[1]) - (bz - az) * (ax - point[0])) / length)
    return worst


def mass(part: PlacedPart) -> int:
    return part.shape.cells


def centre(part: PlacedPart) -> Point:
    return (part.x + part.shape.size_x / 2, part.z + part.shape.size_z / 2)


def ground_corners(part: PlacedPart) -> list[Point]:
    """The corners of the part's footprint if it stands on the ground (its footprint is a rectangle)."""
    if part.layer != 0:
        return []
    x0, z0, x1, z1 = part.x, part.z, part.x + part.shape.size_x, part.z + part.shape.size_z
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


@dataclass
class Cluster:
    mass: float = 0.0
    moment_x: float = 0.0  # sum of mass * x
    moment_z: float = 0.0
    hull: list[Point] = field(default_factory=list)  # of the ground contacts

    def merged(self, others: Iterable["Cluster"], part: PlacedPart | None = None) -> "Cluster":
        clusters = [self, *others]
        m = sum(c.mass for c in clusters)
        mx = sum(c.moment_x for c in clusters)
        mz = sum(c.moment_z for c in clusters)
        points = [p for c in clusters for p in c.hull]
        if part is not None:
            cx, cz = centre(part)
            m, mx, mz = m + mass(part), mx + mass(part) * cx, mz + mass(part) * cz
            points += ground_corners(part)
        return Cluster(m, mx, mz, convex_hull(points))

    def tip_distance(self) -> float:
        """How far the centre of mass lies outside the ground hull (<= 0: the cluster stands)."""
        if len(self.hull) < 3:
            return float("inf")
        return outside_distance((self.moment_x / self.mass, self.moment_z / self.mass), self.hull)

    def stands(self) -> bool:
        return self.tip_distance() <= TOLERANCE


class Balance:
    """Clusters of the parts placed so far, by part index (in placement order)."""

    def __init__(self) -> None:
        self.parent: list[int] = []
        self.clusters: dict[int, Cluster] = {}  # root -> cluster

    def root(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def joined(self, part: PlacedPart, below: Iterable[int]) -> Cluster:
        """The cluster ``part`` would form with the clusters of the parts it rests on (``below``)."""
        roots = {self.root(i) for i in below}
        return Cluster().merged((self.clusters[r] for r in sorted(roots)), part)

    def can_add(self, part: PlacedPart, below: Iterable[int]) -> bool:
        return self.joined(part, below).stands()

    def add(self, part: PlacedPart, below: Iterable[int]) -> None:
        """Record ``part`` (the next index) resting on the parts ``below``."""
        below = list(below)
        cluster = self.joined(part, below)
        index = len(self.parent)
        self.parent.append(index)
        for r in {self.root(i) for i in below}:
            self.parent[r] = index
            del self.clusters[r]
        self.clusters[index] = cluster


def clusters(placed: Sequence[PlacedPart]) -> list[tuple[list[int], Cluster]]:
    """The final clusters of a build: (indices into ``placed``, cluster), largest first."""
    owner: dict[tuple[int, int, int], int] = {}
    for i, part in enumerate(placed):
        for cell in part.cells():
            owner[cell] = i
    order = sorted(range(len(placed)), key=lambda i: placed[i].layer)
    balance, position = Balance(), {}
    for i in order:
        part = placed[i]
        below = {position[owner[(y - 1, z, x)]] for y, z, x in part.bottom_cells() if (y - 1, z, x) in owner}
        position[i] = len(balance.parent)
        balance.add(part, below)
    members: dict[int, list[int]] = {}
    for i in order:
        members.setdefault(balance.root(position[i]), []).append(i)
    found = [(sorted(m), balance.clusters[root]) for root, m in members.items()]
    return sorted(found, key=lambda item: -len(item[0]))
