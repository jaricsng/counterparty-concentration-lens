"""Macro / multi-factor correlated stress (M1)."""

from __future__ import annotations

from lens_m1 import datasets, macro


def test_sector_sensitivity_differentiates() -> None:
    # CRE is most property-sensitive; government is resilient
    assert macro.entity_notches("commercial real estate", "property_crash") == 4
    assert macro.entity_notches("government", "property_crash") == 0
    assert macro.entity_notches("financial services", "rates_shock") >= 2


def test_apply_macro_is_pure_and_downgrades() -> None:
    s = datasets.get_dataset("stressed")
    before = [e.rating for e in s.entities]
    shocked = macro.apply_macro(s, "recession")
    assert [e.rating for e in s.entities] == before  # input unchanged
    # at least the CRE/financials names moved
    assert any(a.rating != b.rating for a, b in zip(s.entities, shocked.entities, strict=True))


def test_every_macro_scenario_raises_expected_loss() -> None:
    s = datasets.get_dataset("stressed")
    base, _ = macro.compare(s, "recession")
    for key in macro.MACRO_SCENARIOS:
        assert macro.compare(s, key)[1].total_el > base.total_el


def test_property_crash_hits_cre_hardest() -> None:
    impacts = macro.sector_impacts(datasets.get_dataset("stressed"), "property_crash")
    assert impacts[0].sector == "commercial real estate"  # biggest EL delta
    assert impacts[0].notches == 4
