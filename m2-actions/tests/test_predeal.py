"""Pre-deal limit checks — dynamic / tenor / settlement (M2)."""

from __future__ import annotations

from lens_m1 import datasets, rdfize
from lens_m2 import predeal
from lens_m2.store import InMemoryStore


def _store(name: str = "stressed") -> InMemoryStore:
    return InMemoryStore(rdfize.build_graph(datasets.get_dataset(name)))


def test_proposed_deal_can_breach_connected_limit() -> None:
    # Acme (LE-0001): connected ~34M already > its 25M limit -> any new deal breaches
    v = predeal.pre_deal_check(_store(), borrower_id="LE-0001", amount=5_000_000, tenor=3)
    assert not v.limit_ok and v.connected_post > v.effective_limit
    assert not v.ok and any("connected limit" in r for r in v.reasons)


def test_tenor_cap_enforced() -> None:
    v = predeal.pre_deal_check(_store(), borrower_id="LE-0044", amount=1_000_000, tenor=10)
    assert not v.tenor_ok and v.tenor_cap == 7
    assert any("tenor" in r for r in v.reasons)


def test_dynamic_limit_tightens_for_sub_investment_grade() -> None:
    # Vortex Alpha (LE-0021, BB) -> effective limit = base × 0.80 < base
    v = predeal.pre_deal_check(_store(), borrower_id="LE-0021", amount=1, tenor=1)
    assert v.rating == "BB"
    assert v.effective_limit == v.base_limit * predeal.RATING_LIMIT_FACTOR["BB"]
    assert v.effective_limit < v.base_limit


def test_settlement_sublimit() -> None:
    v = predeal.pre_deal_check(_store(), borrower_id="LE-0044", amount=1_000_000, tenor=3)
    assert v.settlement_limit == v.effective_limit * predeal.SETTLEMENT_FRACTION
    huge = predeal.pre_deal_check(_store(), borrower_id="LE-0044", amount=999_000_000, tenor=3)
    assert not huge.settlement_ok


def test_headroom_and_ok_for_a_small_deal() -> None:
    v = predeal.pre_deal_check(_store(), borrower_id="LE-0044", amount=1_000_000, tenor=3)
    assert v.headroom == v.effective_limit - v.connected_post
    assert v.ok  # small deal to a name with room, short tenor
