"""Simplified credit-risk layer (M1): EAD, Expected Loss, capital."""

from __future__ import annotations

from decimal import Decimal

from lens_m1 import credit_risk as cr
from lens_m1 import datasets


def test_pd_and_risk_weight_tables() -> None:
    assert cr.pd_for("BB") == Decimal("0.01")
    assert cr.pd_for("CCC") == Decimal("0.20")
    assert cr.pd_for(None) == cr.UNRATED_PD  # unrated -> BB-equivalent
    assert cr.rw_for("BBB") == Decimal("1.00")
    assert cr.rw_for("AAA") == Decimal("0.20")
    assert cr.rw_for("CCC") == Decimal("1.50")


def test_expected_loss_hand_worked() -> None:
    s = datasets.get_dataset("stressed")
    helios = cr.credit_risk(s, "LE-0011")  # BB, EAD 5M (post-collateral)
    assert float(helios.ead) == 5_000_000
    assert float(helios.el) == 22_500  # 0.01 * 0.45 * 5M
    assert float(helios.capital) == 400_000  # 0.08 * 1.0 * 5M
    draco = cr.credit_risk(s, "LE-0047")  # B, EAD 8M -> dominates EL
    assert float(draco.el) == 180_000  # 0.05 * 0.45 * 8M


def test_sub_investment_grade_drives_expected_loss() -> None:
    s = datasets.get_dataset("stressed")
    rows = cr.portfolio_credit_risk(s)  # sorted by EL desc
    assert rows[0].rating in ("B", "CCC")  # the worst grades top the EL table


def test_portfolio_summary() -> None:
    ps = cr.portfolio_summary(datasets.get_dataset("stressed"))
    assert round(float(ps.total_el)) == 811_287
    assert round(float(ps.total_capital)) == 10_657_600
    assert round(float(ps.capital_as_pct_of_eligible) * 100, 1) == 10.7
