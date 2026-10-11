"""M12c: a hollow target cut from the solid target at the solid's scale (``--hollow-scale solid``) keeps the object's
size and frees the interior's share of the part budget; the shell scale (the default) is unchanged."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from brickwfc.alt.features import exposed
from brickwfc.alt.pipeline import AltConfig, resolve, scaled_target, sized_target
from brickwfc.bricks.colors import colors_by_name
from brickwfc.bricks.shapes import hollow

BOX = "\n".join(f"2x2 ({x},{y},{z})" for z in range(4) for x in (0, 2, 4) for y in (0, 2, 4))  # a 6 x 6 x 4 solid box


def box_source(tmp_path, cells: int = 1500, extra: dict | None = None):
    path = tmp_path / "box.txt"
    path.write_text(BOX + "\n", encoding="utf-8")
    source = SimpleNamespace(inventory={("plate1x1", "red"): cells, **(extra or {})},
                             colors=tuple(colors_by_name(["red"])))
    return source, AltConfig(shape=str(path))


@pytest.mark.parametrize("thickness", [1, 2])
def test_solid_scale_keeps_the_grid_and_removes_interior_cells(tmp_path, thickness: int) -> None:
    source, config = box_source(tmp_path)
    solid, solid_info = sized_target(source, config)
    shell, info = sized_target(source, replace(config, hollow=thickness, hollow_scale="solid"))
    assert shell.mask.shape == solid.mask.shape and not (shell.mask & ~solid.mask).any()  # the same object, less
    assert (exposed(shell.mask) == exposed(solid.mask)).all()  # the outside is kept: the void is enclosed
    assert (shell.mask == hollow(solid.mask, thickness)).all()  # a box has no support columns
    details = info["hollow"]
    assert details["thickness"] == thickness and details["scale"] == "solid"
    assert details["solid_cells"] == solid.mask.sum() and details["cells"] == shell.mask.sum()
    assert details["removed"] == solid.mask.sum() - shell.mask.sum() > 0
    assert details["budget_cells"] == 1500 and details["fit_nowhere"] == {} and details["fit_nowhere_cells"] == 0
    assert info["volume"] == solid_info["volume"]  # sized as the solid


def test_a_thicker_shell_keeps_more(tmp_path) -> None:
    source, config = box_source(tmp_path)
    one, _ = sized_target(source, replace(config, hollow=1, hollow_scale="solid"))
    two, _ = sized_target(source, replace(config, hollow=2, hollow_scale="solid"))
    assert one.mask.sum() < two.mask.sum() and not (one.mask & ~two.mask).any()


def test_shell_scale_is_unchanged(tmp_path) -> None:
    source, config = box_source(tmp_path)
    default, info = sized_target(source, replace(config, hollow=2))
    explicit, _ = sized_target(source, replace(config, hollow=2, hollow_scale="shell"))
    direct = scaled_target(source, resolve(replace(config, hollow=2)), info["volume"], tmp_path)
    assert (default.mask == explicit.mask).all() and (default.mask == direct.mask).all() and "hollow" not in info
    solid, _ = sized_target(source, config)
    assert default.mask.shape != solid.mask.shape  # the shell is scaled up to the volume: a larger object
    # without a hollow, the scale option changes nothing
    plain, _ = sized_target(source, replace(config, hollow_scale="solid"))
    assert (plain.mask == solid.mask).all()


def test_parts_that_fit_nowhere_in_the_shell_are_counted(tmp_path) -> None:
    source, config = box_source(tmp_path, extra={("brick2x4", "red"): 2})
    _, info = sized_target(source, replace(config, hollow=1, hollow_scale="solid"))
    assert "brick2x4" not in info["left_out"]  # it fits in the solid box ...
    details = info["hollow"]  # ... but nowhere in a 1-cell shell with 2 x 2 pillars: counted, the scale is kept
    assert details["fit_nowhere"] == {"brick2x4": 2} and details["fit_nowhere_cells"] == 2 * 24
    assert details["budget_cells"] == 1500 + 2 * 24


def test_unknown_hollow_scale(tmp_path) -> None:
    source, config = box_source(tmp_path)
    with pytest.raises(ValueError):
        sized_target(source, replace(config, hollow=2, hollow_scale="box"))
