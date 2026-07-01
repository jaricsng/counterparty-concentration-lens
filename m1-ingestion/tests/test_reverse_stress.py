"""Reverse stress testing — mildest shock to a target (M1)."""

from __future__ import annotations

from decimal import Decimal

from lens_m1 import credit_risk, datasets
from lens_m1 import reverse_stress as rs


def test_monotone_in_downgrade_severity() -> None:
    s = datasets.get_dataset("stressed")
    els = [float(credit_risk.portfolio_summary(rs._downgrade_all(s, n)).total_el) for n in range(5)]
    assert els == sorted(els)  # more severe never lowers EL


def test_double_expected_loss_is_feasible() -> None:
    s = datasets.get_dataset("stressed")
    r = rs.multiplier_target(s, "expected_loss", 2.0)
    assert r.feasible and r.family == "downgrade"
    assert r.achieved >= r.target and r.base_value < r.target


def test_limit_breaches_use_exposure_family() -> None:
    s = datasets.get_dataset("stressed")
    r = rs.min_shock(s, "limit_breaches", Decimal(6))
    assert r.family == "exposure" and r.feasible
    assert r.achieved >= 6 and r.base_value < 6
    assert r.shock_label.endswith("exposure uplift")


def test_infeasible_within_cap_is_reported() -> None:
    s = datasets.get_dataset("stressed")
    r = rs.min_shock(s, "expected_loss", Decimal("10_000_000_000"), max_severity=3)
    assert not r.feasible and r.severity is None
