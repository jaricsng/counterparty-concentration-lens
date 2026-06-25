"""Country + rating concentration shares (M1 metrics)."""

from __future__ import annotations

from decimal import Decimal

from lens_m1 import datasets, metrics


def _is_one(shares: dict[str, Decimal]) -> bool:
    return abs(sum(shares.values(), Decimal(0)) - Decimal(1)) < Decimal("0.01")


def test_country_shares_concentrated_in_home_market() -> None:
    cs = metrics.country_shares(datasets.get_dataset("stressed"))
    assert _is_one(cs)
    assert max(cs, key=lambda k: cs[k]) == "SG"
    assert round(float(cs["SG"]), 2) == 0.76  # home-market country concentration


def test_rating_shares_dominated_by_sub_investment_grade() -> None:
    rs = metrics.rating_shares(datasets.get_dataset("stressed"))
    assert _is_one(rs)
    assert max(rs, key=lambda k: rs[k]) == "BB"
    assert round(float(rs["BB"]), 2) == 0.56
    sub_ig = sum((v for k, v in rs.items() if k in ("BB", "B", "CCC")), Decimal(0))
    assert float(sub_ig) > 0.5  # majority of exposure is sub-investment-grade


def test_shares_attributed_to_risk_owner() -> None:
    # The Vortex NBFI cluster (HK) shows up via attribution, not just direct borrowers.
    cs = metrics.country_shares(datasets.get_dataset("stressed"))
    assert "HK" in cs and float(cs["HK"]) > 0.1
