"""Static-equilibrium stability check for plate builds (M7), in the spirit of Legolization / BrickGPT.

Model (vertical forces only; parts are rigid):

- Each part weighs one unit per cell it covers (a brick is 3 plate cells tall), acting at the centroid of
  its footprint (a slope counts as its full box).
- Where a part's bottom layer rests on a part below (or on the ground) the faces touch over that cell
  (flat-bottomed cells only: an inverted slope's underside touches nothing):
  - **compression**: 4 push-only forces at the cell corners (contact pressure can act anywhere on the face);
  - **clutch**: 4 pull-only forces on the stud ring (radius ``STUD_RADIUS`` of a stud pitch) that hold
    the upper part down onto the lower one. The ground, tiles and slope faces have no studs, so they can only push.
- Every part must be in equilibrium: net vertical force and net torque about both horizontal axes are zero.

``required_clutch`` solves a linear program for the smallest clutch per stud that makes some force
assignment satisfy all of this. 0 means the build stands with no grip at all (pure stacking); ``inf``
means no clutch helps (a floating part, or the build would tip over its ground contact). Units are
one plate-cell weight. Horizontal forces, friction and part flex are not modelled.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from brickwfc.bricks.parts import PlacedPart

STUD_RADIUS = 0.3  # stud radius / stud pitch (2.4 mm / 8 mm)
CORNERS = ((-0.5, -0.5), (-0.5, 0.5), (0.5, -0.5), (0.5, 0.5))
STUD_POINTS = tuple((dx, dz) for dx in (-STUD_RADIUS, STUD_RADIUS) for dz in (-STUD_RADIUS, STUD_RADIUS))
ZERO_TOLERANCE = 1e-7


def part_occupancy(placed: list[PlacedPart], shape: tuple[int, int, int]) -> np.ndarray:
    """(Y, Z, X) array of part indices into ``placed``, -1 where empty."""
    owner = np.full(shape, -1, dtype=np.int64)
    for i, part in enumerate(placed):
        for cell in part.cells():
            owner[cell] = i
    return owner


def required_clutch(placed: list[PlacedPart], shape: tuple[int, int, int], baseplate: bool = False,
                    method: str = "highs") -> float:
    """Smallest clutch per stud (in plate-cell weights) for which the build is in static equilibrium.

    By default the build stands on a table (the ground only pushes). With ``baseplate=True`` it is
    clicked onto a studded baseplate, so ground contacts can also pull (with the same clutch limit).
    ``method`` is the ``scipy.optimize.linprog`` solver. ``"highs-ipm"`` (interior point) is much faster on
    tall builds of 1000+ parts (M12: 5 s instead of minutes) and agrees to rounding; the default
    keeps the M7-M11 tables reproducible.
    """
    if not placed:
        return 0.0
    owner = part_occupancy(placed, shape)
    centres = [part.centre() for part in placed]
    studs = {cell for part in placed for cell in part.stud_cells()}

    # Each force variable acts upward on ``upper`` and downward on ``lower`` (-1 = ground) at (x, z).
    # Compression variables are >= 0. Clutch variables are >= 0 too but act the other way (pulling the
    # upper part down), so they enter the equations with sign -1 and are bounded by the clutch limit t.
    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    clutch_vars: list[int] = []
    n_vars = 0

    def add_force(upper: int, lower: int, x: float, z: float, sign: float) -> None:
        nonlocal n_vars
        for part, direction in ((upper, sign), (lower, -sign)):
            if part < 0:
                continue
            centre_x, centre_z = centres[part]
            for row_offset, arm in enumerate((1.0, x - centre_x, z - centre_z)):
                rows.append(3 * part + row_offset)
                cols.append(n_vars)
                values.append(direction * arm)
        n_vars += 1

    for i, part in enumerate(placed):
        for y, z, x in part.seated_cells():
            lower = -1 if y == 0 else int(owner[y - 1, z, x])
            if y > 0 and lower < 0:
                continue  # nothing below this stud
            cx, cz = x + 0.5, z + 0.5
            for dx, dz in CORNERS:
                add_force(i, lower, cx + dx, cz + dz, sign=1.0)
            if (lower >= 0 and (y - 1, z, x) in studs) or (lower < 0 and baseplate):
                for dx, dz in STUD_POINTS:
                    clutch_vars.append(n_vars)
                    add_force(i, lower, cx + dx, cz + dz, sign=-1.0)

    # Equilibrium: forces on each part balance its weight; torques balance about its centre.
    n_eq = 3 * len(placed)
    a_eq = coo_matrix((values, (rows, cols)), shape=(n_eq, n_vars + 1)).tocsr()
    b_eq = np.zeros(n_eq)
    b_eq[0::3] = [len(part.cells()) for part in placed]

    # Clutch limit: every clutch force - t <= 0; minimise t (the last variable).
    t_col = n_vars
    a_ub, b_ub = None, None
    if clutch_vars:
        k = len(clutch_vars)
        limit_rows = list(range(k)) * 2
        limit_cols = clutch_vars + [t_col] * k
        a_ub = coo_matrix(([1.0] * k + [-1.0] * k, (limit_rows, limit_cols)), shape=(k, n_vars + 1)).tocsr()
        b_ub = np.zeros(k)
    cost = np.zeros(n_vars + 1)
    cost[t_col] = 1.0

    result = linprog(cost, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=(0, None), method=method)
    if result.status == 2:  # infeasible
        return math.inf
    if result.status != 0:
        raise RuntimeError(f"physics LP failed: {result.message}")
    per_point = float(result.x[t_col])
    per_stud = len(STUD_POINTS) * per_point
    return 0.0 if per_stud < ZERO_TOLERANCE else per_stud


def is_physically_stable(placed: list[PlacedPart], shape: tuple[int, int, int], clutch: float, baseplate: bool = False) -> bool:
    return required_clutch(placed, shape, baseplate) <= clutch


def tipping_clusters(placed: list[PlacedPart]) -> list[tuple[list[int], float]]:
    """Why a build needs infinite clutch: its clusters of stud-connected parts whose centre of mass lies
    outside their ground contacts' convex hull, as (indices into ``placed``, distance outside in studs).
    Empty iff ``required_clutch`` is finite (see ``balance``)."""
    from brickwfc.bricks.balance import clusters

    return [(members, c.tip_distance()) for members, c in clusters(placed) if not c.stands()]


def table_clutch(placed: list[PlacedPart], shape: tuple[int, int, int]) -> float:
    """``required_clutch`` on a table, faster on large builds (M12): infinite if a cluster tips over
    (``tipping_clusters``, exact), else the LP by interior point, falling back to the default solver if
    that fails."""
    if tipping_clusters(placed):
        return math.inf
    try:
        return required_clutch(placed, shape, method="highs-ipm")
    except RuntimeError:
        return required_clutch(placed, shape)
