"""Netting + collateral: net exposure = max(0, gross - eligible mitigant).

Eligible mitigant = value * (1 - haircut); netting is one set per counterparty,
so collateral shared across counterparties is excluded (no allocation guesswork).
"""

from __future__ import annotations

from decimal import Decimal

from lens_m1 import datasets, metrics
from lens_m1.spec import Collateral, DatasetSpec, Loan


def _spec(loans: list[Loan], collateral: list[Collateral]) -> DatasetSpec:
    return DatasetSpec("t", [], loans, [], collateral, [])


def test_collateral_reduces_exposure_by_value_after_haircut() -> None:
    spec = _spec(
        [Loan("LN-1", "LE-BANK", "LE-A", 1000)],
        [Collateral("C-1", "warehouse", "LE-A", ("LN-1",), collateral_value=1000, haircut_pct=25)],
    )
    assert metrics.collateral_mitigant(spec, "LE-A") == Decimal(750)  # 1000 * (1 - 0.25)
    assert metrics.net_exposure(spec, "LE-A") == Decimal(250)


def test_over_collateralised_floors_at_zero() -> None:
    spec = _spec(
        [Loan("LN-1", "LE-BANK", "LE-A", 1000)],
        [Collateral("C-1", "cash", "LE-A", ("LN-1",), collateral_value=2000, haircut_pct=0)],
    )
    assert metrics.net_exposure(spec, "LE-A") == Decimal(0)


def test_collateral_without_a_value_does_not_net() -> None:
    spec = _spec(
        [Loan("LN-1", "LE-BANK", "LE-A", 1000)],
        [Collateral("C-1", "warehouse", "LE-A", ("LN-1",))],
    )
    assert metrics.net_exposure(spec, "LE-A") == Decimal(1000)


def test_collateral_shared_across_counterparties_is_excluded() -> None:
    spec = _spec(
        [Loan("LN-1", "LE-BANK", "LE-A", 1000), Loan("LN-2", "LE-BANK", "LE-B", 1000)],
        [Collateral("C-1", "shared", "LE-A", ("LN-1", "LN-2"), collateral_value=1000)],
    )
    assert metrics.net_exposure(spec, "LE-A") == Decimal(1000)
    assert metrics.net_exposure(spec, "LE-B") == Decimal(1000)


def test_stressed_oracle_net_exposure() -> None:
    s = datasets.get_dataset("stressed")
    assert metrics.net_exposure(s, "LE-0011") == Decimal(5_000_000)  # 7M - 4M*(1-0.5)
    assert metrics.net_exposure(s, "LE-0021") == Decimal(4_000_000)  # 8M - 5M*(1-0.2)
    assert metrics.net_exposure(s, "LE-0044") == metrics.direct_exposure(s, "LE-0044")  # no collat
    assert metrics.net_exposure(s, "LE-0001") == Decimal(5_000_000)  # shared collat excluded


def test_stressed_richer_collateralised_set() -> None:
    s = datasets.get_dataset("stressed")
    assert metrics.net_exposure(s, "LE-0042") == Decimal(1_100_000)  # gov: 3M - 2M*0.95
    assert metrics.net_exposure(s, "LE-0040") == Decimal(1_500_000)  # CRE: 3M - 2M*0.75
    assert metrics.net_exposure(s, "LE-0043") == Decimal(4_600_000)  # health: 7M - 4M*0.60
    assert metrics.net_exposure(s, "LE-0030") == Decimal(2_900_000)  # NBFI: 5M - 3M*0.70
