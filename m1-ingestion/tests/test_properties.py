"""Property-based invariants for the concentration math (Hypothesis).

The oracle tests pin exact values on the two bundled datasets; these assert the
*laws* HHI and CR10 must obey for ANY exposure distribution, so a refactor that
happens to still match calm/stressed but breaks the maths is caught.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from lens_m1.metrics import cr10, hhi

# A positive exposure vector: {name -> amount}, amounts are positive decimals.
vectors = st.lists(st.integers(min_value=1, max_value=10**9), min_size=1, max_size=40).map(
    lambda vals: {f"e{i}": Decimal(v) for i, v in enumerate(vals)}
)

_EPS = Decimal("1e-9")


@given(vectors)
def test_hhi_is_in_the_unit_interval(vector: dict[str, Decimal]) -> None:
    h = hhi(vector)
    assert h > 0
    assert h <= 1 + _EPS


@given(vectors)
def test_cr10_is_in_the_unit_interval(vector: dict[str, Decimal]) -> None:
    c = cr10(vector)
    assert c > 0
    assert c <= 1 + _EPS


@given(vectors)
def test_hhi_is_at_least_inverse_n(vector: dict[str, Decimal]) -> None:
    # HHI is minimised by a perfectly even book, where it equals 1/n.
    assert hhi(vector) >= Decimal(1) / len(vector) - _EPS


@given(st.integers(min_value=1, max_value=10**9))
def test_single_name_is_fully_concentrated(amount: int) -> None:
    vector = {"only": Decimal(amount)}
    assert hhi(vector) == 1
    assert cr10(vector) == 1


@given(st.lists(st.integers(min_value=1, max_value=10**9), min_size=1, max_size=10))
def test_cr10_is_one_for_ten_or_fewer_names(values: list[int]) -> None:
    vector = {f"e{i}": Decimal(v) for i, v in enumerate(values)}
    assert cr10(vector) == 1


@given(vectors, st.integers(min_value=2, max_value=10_000))
def test_metrics_depend_on_shares_not_absolute_size(
    vector: dict[str, Decimal], factor: int
) -> None:
    # scaling every exposure by the same factor leaves both ratios unchanged
    scaled = {k: v * factor for k, v in vector.items()}
    assert abs(hhi(vector) - hhi(scaled)) < _EPS
    assert abs(cr10(vector) - cr10(scaled)) < _EPS
