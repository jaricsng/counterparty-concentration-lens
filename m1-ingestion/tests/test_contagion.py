"""Deterministic systemic-contagion cascade (M1)."""

from __future__ import annotations

from lens_m1 import contagion, datasets


def test_nbfi_guarantor_amplifies_via_contagion() -> None:
    s = datasets.get_dataset("stressed")
    nimbus = contagion.cascade(s, "LE-0030")  # guarantees 6 large outside loans
    assert nimbus.contagion_loss > nimbus.direct_loss
    assert nimbus.amplification > 1
    assert nimbus.total_loss == nimbus.direct_loss + nimbus.contagion_loss


def test_nimbus_is_most_systemic() -> None:
    ranking = contagion.systemic_ranking(datasets.get_dataset("stressed"))
    assert ranking[0].seed == "LE-0030"  # small direct, huge connected -> top systemic
    assert ranking == sorted(ranking, key=lambda c: c.total_loss, reverse=True)


def test_standalone_name_has_no_contagion() -> None:
    s = datasets.get_dataset("stressed")
    # Orion (LE-0040): a standalone borrower that guarantees nothing
    orion = contagion.cascade(s, "LE-0040")
    assert orion.contagion_loss == 0
    assert orion.amplification == 1


def test_solvent_guarantor_recovers_direct_loss() -> None:
    s = datasets.get_dataset("stressed")
    # Borealis (LE-0045) borrows LN-1005, guaranteed by Acme (solvent if Borealis seeds).
    borealis = contagion.cascade(s, "LE-0045")
    # its guaranteed loan is recovered by the solvent guarantor -> no direct loss on it
    assert borealis.direct_loss == 0
