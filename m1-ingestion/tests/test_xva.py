"""Forward-looking exposure (PFE/EE) + CVA (M1, analytical)."""

from __future__ import annotations

from lens_m1 import datasets, xva


def test_profile_at_t0_equals_current_exposure() -> None:
    prof = xva.exposure_profile(8_000_000, 7)
    assert prof[0].ee == 8_000_000 and prof[0].pfe == 8_000_000


def test_pfe_humps_above_current_exposure() -> None:
    prof = xva.exposure_profile(8_000_000, 7)
    assert max(p.pfe for p in prof) > prof[0].pfe  # diffusion add-on -> hump
    assert prof[-1].ee < prof[0].ee  # amortises toward maturity


def test_cva_rises_with_pd_and_zero_for_zero_pd() -> None:
    assert xva.cva(8_000_000, 7, 0.0) == 0.0
    assert xva.cva(8_000_000, 7, 0.20) > xva.cva(8_000_000, 7, 0.01)


def test_cva_zero_when_no_exposure() -> None:
    assert xva.cva(0.0, 5, 0.20) == 0.0


def test_sub_investment_grade_long_tenor_dominates_cva() -> None:
    rows = xva.portfolio_xva(datasets.get_dataset("stressed"))
    assert rows[0].rating in ("B", "CCC", "BB")  # worst grades top the CVA table
    assert rows[0].cva == max(r.cva for r in rows)


def test_total_cva_positive() -> None:
    assert float(xva.total_cva(datasets.get_dataset("stressed"))) > 0


def test_full_xva_components_positive_and_identity() -> None:
    s = datasets.get_dataset("stressed")
    r = xva.counterparty_xva_breakdown(s, "LE-0022")  # B, 8M, 7y
    assert r.fva > 0 and r.mva > 0 and r.kva > 0 and r.cva > 0
    assert r.dva < r.cva  # one-directional loan book -> DVA tiny
    assert r.total_xva == r.cva - r.dva + r.fva + r.mva + r.kva


def test_kva_rises_with_risk_weight() -> None:
    s = datasets.get_dataset("stressed")
    # B (RW 1.5) vs A (RW 0.5) at similar EAD/tenor -> higher KVA for the worse grade
    b_name = next(r for r in xva.portfolio_xva_breakdown(s) if r.rating == "B")
    assert b_name.kva > 0


def test_portfolio_breakdown_sorted_by_total() -> None:
    rows = xva.portfolio_xva_breakdown(datasets.get_dataset("stressed"))
    assert rows == sorted(rows, key=lambda r: r.total_xva, reverse=True)
