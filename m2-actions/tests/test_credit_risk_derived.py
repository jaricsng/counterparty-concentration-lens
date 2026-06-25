"""Live-store credit-risk (M2 derived) matches the M1 oracle."""

from __future__ import annotations

from lens_m1 import credit_risk as cr
from lens_m1 import datasets, rdfize
from lens_m2 import derived
from lens_m2.store import InMemoryStore


def _store(name: str) -> InMemoryStore:
    return InMemoryStore(rdfize.build_graph(datasets.get_dataset(name)))


def test_expected_losses_match_m1_oracle() -> None:
    m1 = {r.entity: r for r in cr.portfolio_credit_risk(datasets.get_dataset("stressed"))}
    m2 = {r.entity: r for r in derived.expected_losses(_store("stressed"))}
    assert set(m1) == set(m2)
    for e in m1:
        assert m2[e].ead == m1[e].ead
        assert m2[e].el == m1[e].el
        assert m2[e].capital == m1[e].capital
        assert m2[e].rating == m1[e].rating


def test_capital_summary_totals() -> None:
    cs = derived.capital_summary(_store("stressed"))
    assert round(float(cs.total_el)) == 811_287
    assert round(float(cs.total_capital)) == 10_657_600
