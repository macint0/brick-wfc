"""M13: diversity of a set of designs (mean pairwise distance, effective number of designs)."""

import numpy as np
import pytest

from brickwfc.funnel.dedupe import dedupe
from brickwfc.funnel.diversity import (diversity, effective_number, mean_pairwise_distance, pairwise_distances,
                                       similarity)


def groups(sizes: list[int], spread: float = 0.001, gap: float = 1.0, dims: int = 5, seed: int = 0) -> np.ndarray:
    """Points in well-separated groups of the given sizes."""
    rng = np.random.default_rng(seed)
    rows = [gap * k * np.eye(dims)[k % dims] * (1 + k // dims) + spread * rng.standard_normal((n, dims))
            for k, n in enumerate(sizes)]
    return np.concatenate(rows)


def test_pairwise_distances_and_mean() -> None:
    f = np.array([[0.0, 0.0], [3.0, 4.0], [0.0, 4.0]])
    d = pairwise_distances(f)
    assert d[0, 1] == pytest.approx(5) and d[1, 2] == pytest.approx(3) and np.allclose(d, d.T) and not d.diagonal().any()
    assert mean_pairwise_distance(f) == pytest.approx((5 + 4 + 3) / 3)
    assert mean_pairwise_distance(f[:1]) == 0.0


def test_effective_number_extremes() -> None:
    distinct = np.eye(6)
    assert effective_number(distinct, threshold=0.5) == pytest.approx(6)
    same = np.ones((6, 3))
    assert effective_number(same, threshold=0.5) == pytest.approx(1)
    assert effective_number(np.zeros((0, 3)), threshold=0.5) == 0.0


@pytest.mark.parametrize("sizes", [[4, 4, 4], [10, 1, 1], [3, 7], [5]])
def test_effective_number_is_the_hill_number_of_groups(sizes: list[int]) -> None:
    p = np.array(sizes) / sum(sizes)
    hill = np.exp(-(p * np.log(p)).sum())
    assert effective_number(groups(sizes), threshold=0.1) == pytest.approx(hill)


def test_effective_number_counts_what_dedupe_keeps_for_clean_groups() -> None:
    f = groups([3, 3, 3, 3])
    assert len(dedupe(f, 0.1)) == 4 and effective_number(f, 0.1) == pytest.approx(4)


def test_exp_kernel_is_smooth_and_bounded() -> None:
    f = groups([4, 4], spread=0.0, gap=1.0)
    near, far = effective_number(f, 0.01, "exp"), effective_number(f, 100.0, "exp")
    assert near == pytest.approx(2, abs=1e-6) and 1 <= far < 1.05
    z = similarity(pairwise_distances(f), 0.5, "exp")
    assert z.max() == 1 and (z > 0).all()
    with pytest.raises(ValueError):
        similarity(pairwise_distances(f), 0.0)
    with pytest.raises(ValueError):
        similarity(pairwise_distances(f), 1.0, "gauss")  # type: ignore[arg-type]


def test_diversity_summary() -> None:
    result = diversity(groups([2, 2]), threshold=0.1)
    assert result.designs == 4 and result.effective == pytest.approx(2) and result.effective_share == pytest.approx(0.5)
    assert result.mean_distance == pytest.approx(mean_pairwise_distance(groups([2, 2])))
