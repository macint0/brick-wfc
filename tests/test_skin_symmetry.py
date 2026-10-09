"""M12b step 3: skin and mirror-symmetry measures."""

import math

import numpy as np

from brickwfc.bricks.parts import CATALOG, PlacedPart, Shape, shapes_of
from brickwfc.bricks.skin import exterior, size_class, skin
from brickwfc.bricks.symmetry import Plane, mirror_part, mirror_plane, mirror_shape, part_symmetry, reflected
from brickwfc.experiments.skins import sheet_label
from conftest import BLUE, RED


def placed(name: str, layer: int, x: int, z: int, turn: int = 0, color=RED) -> PlacedPart:
    return PlacedPart(Shape(CATALOG[name], turn), color, layer, x, z)


def test_size_classes() -> None:
    assert size_class(Shape(CATALOG["plate1x2"])) == "small"
    assert size_class(Shape(CATALOG["brick1x4"])) == "long"
    assert size_class(Shape(CATALOG["plate2x4"])) == "wide"
    assert size_class(Shape(CATALOG["plate2x2_corner"])) == "wide"


def test_one_plate_skin() -> None:
    s = skin([placed("plate2x4", 0, 1, 1)], (3, 4, 6))
    assert s.faces == 8 + 2 * (4 + 2)  # top and four sides; the bottom rests on the table
    assert s.top_faces == 8
    assert s.share == {"small": 0.0, "long": 0.0, "wide": 1.0}
    assert s.faces_per_part == s.faces


def test_touching_faces_and_enclosed_voids_are_not_skin() -> None:
    two = skin([placed("plate1x1", 0, 0, 0), placed("plate1x1", 0, 1, 0)], (1, 1, 2))
    assert two.faces == 2 * 5 - 2  # the shared face is hidden
    # A closed 3 x 3 x 3 box of 1x1 plates with one empty cell inside: the hole's faces are not skin.
    parts = [placed("plate1x1", y, x, z) for y in range(3) for z in range(3) for x in range(3) if (y, z, x) != (1, 1, 1)]
    filled = np.ones((3, 3, 3), dtype=bool)
    filled[1, 1, 1] = False
    assert not exterior(filled)[1, 1, 1]
    assert skin(parts, (3, 3, 3)).faces == 9 * 5


def test_patch_fragmentation() -> None:
    one = skin([placed("plate4x4", 0, 0, 0)], (1, 4, 4))
    assert (one.top_patches, one.top_patch_parts) == (1, 1.0)
    four = skin([placed("plate2x2", 0, x, z) for x in (0, 2) for z in (0, 2)], (1, 4, 4))
    assert (four.top_patches, four.top_patch_parts) == (1, 4.0)
    # A wall of 1 x 4 bricks, 4 studs wide and 2 bricks (6 plates) tall: side windows of 4 plates span 2 bricks.
    wall = skin([placed("brick1x4", y, 0, 0) for y in (0, 3)], (6, 1, 4))
    assert wall.side_patch_parts == 2.0 and wall.side_patches == 2 * 3  # two faces, three window heights
    assert math.isnan(skin([placed("plate1x1", 0, 0, 0)], (1, 1, 1)).top_patch_parts)


def test_mirror_shapes() -> None:
    for shape in shapes_of(list(CATALOG.values())):
        for axis in (1, 2):
            image = mirror_shape(shape, axis)
            assert image is not None, shape.name
            assert mirror_shape(image, axis) == shape
    plate = Shape(CATALOG["plate1x2"])
    assert mirror_shape(plate, 2) == plate
    corner = Shape(CATALOG["plate2x2_corner"])
    assert mirror_shape(corner, 2) != corner and mirror_shape(corner, 1) != corner
    slope = Shape(CATALOG["slope45_2x2"])  # falls toward -z: a mirror across x keeps it, across z turns it
    assert mirror_shape(slope, 2) == slope and mirror_shape(slope, 1) != slope


def test_mirror_part_and_symmetry() -> None:
    plane = Plane(2, 5, 1.0)  # x -> 5 - x
    left = placed("plate1x2", 0, 0, 0)
    right = mirror_part(left, plane)
    assert (right.x, right.z) == (4, 0) and mirror_part(right, plane) == left
    middle = placed("plate2x2", 1, 2, 0)  # covers x = 2, 3: its own mirror image
    assert mirror_part(middle, plane) == middle
    lonely = placed("plate1x1", 2, 0, 0)
    sym = part_symmetry([left, right, middle, lonely], plane, (3, 2, 6))
    assert sym.parts == 0.75 and sym.parts_color == 0.75
    recolored = part_symmetry([left, PlacedPart(right.shape, BLUE, 0, right.x, right.z), middle], plane, (3, 2, 6))
    assert recolored.parts == 1.0 and math.isclose(recolored.parts_color, 1 / 3)


def test_mirror_plane() -> None:
    mask = np.zeros((2, 3, 9), dtype=bool)
    mask[:, :, 2:7] = True
    mask[1, 0, 2] = mask[1, 0, 6] = False  # symmetric across x = 4
    plane = mirror_plane(mask)
    assert plane is not None and (plane.axis, plane.total, plane.score) == (2, 8, 1.0)
    assert (reflected(mask, plane) == mask).all()
    mask[1, 2, 2] = False  # one side only: x still the better plane, but no longer exact
    assert mirror_plane(mask).score < 1.0
    assert mirror_plane(np.zeros((1, 2, 2), dtype=bool)) is None


def test_sheet_label_is_ascii_when_a_window_is_missing() -> None:
    # The comparison sheet's default font has no em dash: a build without an all-skin 4 x 4 top window reads n/a.
    r = {"fill": 0.666, "top_patch_parts": float("nan"), "side_patch_parts": 3.64, "mirrorable_mirrored": 0.56}
    label = sheet_label({"object": "car", "set": "6378-1"}, "both_a1", r)
    assert label.isascii() and "top n/a, sides 3.6" in label and "mirrored 56%" in label
