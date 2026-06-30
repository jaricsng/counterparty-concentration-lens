"""Deterministic stress / scenario engine (M1)."""

from __future__ import annotations

from lens_m1 import datasets
from lens_m1 import scenarios as sc


def test_notch_down() -> None:
    assert sc.notch_down("A", 2) == "BB"  # A -> BBB -> BB
    assert sc.notch_down("CCC", 3) == "CCC"  # floored at the worst grade
    assert sc.notch_down("BB", 1) == "B"
    assert sc.notch_down(None, 1) is None
    assert sc.notch_down("unrated", 1) == "unrated"  # unknown grades pass through


def test_apply_scenario_does_not_mutate_input() -> None:
    s = datasets.get_dataset("stressed")
    before = [e.rating for e in s.entities]
    sc.apply_scenario(s, "broad_downgrade")
    assert [e.rating for e in s.entities] == before


def test_nbfi_downgrade_only_touches_nbfi() -> None:
    s = datasets.get_dataset("stressed")
    shocked = sc.apply_scenario(s, "nbfi_downgrade")
    for base, after in zip(s.entities, shocked.entities, strict=True):
        if base.counterparty_type == "nbfi":
            assert after.rating == sc.notch_down(base.rating, 2)
        else:
            assert after.rating == base.rating


def test_all_shocks_increase_expected_loss() -> None:
    s = datasets.get_dataset("stressed")
    base = sc.snapshot(s, "base")
    for key in ("nbfi_downgrade", "broad_downgrade", "haircut_plus20", "cre_downturn"):
        assert sc.snapshot(s, key).total_el > base.total_el


def test_nbfi_downgrade_hand_worked() -> None:
    s = datasets.get_dataset("stressed")
    # LE-0022 Vortex Beta: B -> CCC on 8M uncollateralised EAD.
    # EL 0.05*0.45*8M = 180k -> 0.20*0.45*8M = 720k.
    deltas = {d.entity: d for d in sc.expected_loss_deltas(s, "nbfi_downgrade")}
    assert deltas["LE-0022"].rating_shocked == "CCC"
    assert float(deltas["LE-0022"].el_base) == 180_000
    assert float(deltas["LE-0022"].el_shocked) == 720_000


def test_haircut_increase_raises_net_ead() -> None:
    s = datasets.get_dataset("stressed")
    assert sc.snapshot(s, "haircut_plus20").total_ead > sc.snapshot(s, "base").total_ead
