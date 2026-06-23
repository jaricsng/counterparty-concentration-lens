"""Hand-checked oracle for the concentration metrics on the engineered data.

These expected values are the acceptance gate for docs/concentration-metrics.md
§6 / §9 and the oracle that M0's SPARQL queries are validated against next.
"""

from __future__ import annotations

from decimal import Decimal

from lens_m1 import metrics as M
from lens_m1.spec import DatasetSpec

HHI_HIGH = Decimal("0.18")
CR10_HIGH = Decimal("0.60")
SECTOR_HIGH = Decimal("0.30")

M_ = Decimal(1_000_000)


# --- Stressed: every engineered case breaches -------------------------------- #


def test_stressed_hidden_single_name_breach(stressed: DatasetSpec) -> None:
    acme = M.connected_exposure(stressed, "LE-0001")
    assert acme.direct == 20 * M_  # under the 25M limit on direct
    assert acme.total == 34 * M_  # over once connected (guarantee + shared collateral)
    util = {u.name: u for u in M.utilisations(stressed)}
    assert util["LE-0001"].band == "red"


def test_stressed_nbfi_cascade(stressed: DatasetSpec) -> None:
    nimbus = M.connected_exposure(stressed, "LE-0030")
    assert nimbus.direct == 5 * M_
    assert nimbus.total == 47 * M_  # cascade dwarfs direct
    assert nimbus.guarantees_given == 42 * M_


def test_stressed_ubo_aggregation_breach(stressed: DatasetSpec) -> None:
    ubo = M.subsidiary_breach_check(stressed, "LE-0020")
    assert ubo["ubo_connected"] == 24 * M_
    assert ubo["ubo_breaches"] is True
    assert ubo["subsidiary_breaches"] == []  # no single subsidiary breaches


def test_stressed_structural_wwr(stressed: DatasetSpec) -> None:
    flags = M.wrong_way_risk_flags(stressed)
    assert len(flags) == 1
    assert flags[0]["loan"] == "LN-1030"
    assert flags[0]["issuer"] == "LE-0010"  # same group as borrower LE-0011


def test_stressed_portfolio_concentration_breaches(stressed: DatasetSpec) -> None:
    av = M.attributed_vector(stressed)
    dv = M.direct_vector(stressed)
    assert M.hhi(av) > HHI_HIGH  # connected HHI high
    assert M.hhi(dv) < HHI_HIGH  # direct looks acceptable
    assert M.cr10(av) > CR10_HIGH  # connected CR10 high
    assert M.cr10(dv) < CR10_HIGH  # direct CR10 acceptable


def test_stressed_sector_concentration(stressed: DatasetSpec) -> None:
    top = max(M.sector_shares(stressed).values())
    assert top > SECTOR_HIGH


def test_stressed_watchlist_has_amber_and_red(stressed: DatasetSpec) -> None:
    bands = [u.band for u in M.utilisations(stressed)]
    assert bands.count("red") == 3
    assert bands.count("amber") == 4  # Helios + three Vortex subs


# --- Calm: everything within normal bands ------------------------------------ #


def test_calm_all_within_bands(calm: DatasetSpec) -> None:
    av = M.attributed_vector(calm)
    assert M.hhi(av) < HHI_HIGH
    assert max(M.sector_shares(calm).values()) < SECTOR_HIGH
    assert M.wrong_way_risk_flags(calm) == []
    assert not M.subsidiary_breach_check(calm, "LE-0020")["ubo_breaches"]


def test_calm_no_limit_breaches(calm: DatasetSpec) -> None:
    assert all(u.band != "red" for u in M.utilisations(calm))


def test_calm_acme_no_breach(calm: DatasetSpec) -> None:
    acme = M.connected_exposure(calm, "LE-0001")
    assert acme.total < 25 * M_


# --- Correctness guards (loops / double counting) ---------------------------- #


def test_ubo_walk_handles_three_level_chain(stressed: DatasetSpec) -> None:
    assert M.ultimate_parent(stressed, "LE-0004") == "LE-0001"
    assert M.ultimate_parent(stressed, "LE-0002") == "LE-0001"


def test_attribution_conserves_total(stressed: DatasetSpec) -> None:
    # Each loan attributed exactly once: attributed total == direct total == book.
    book = sum(
        (Decimal(ln.principal) for ln in stressed.loans if ln.status == "active"), Decimal(0)
    )
    assert sum(M.attributed_vector(stressed).values(), Decimal(0)) == book
    assert sum(M.direct_vector(stressed).values(), Decimal(0)) == book


def test_closed_loans_excluded(stressed: DatasetSpec) -> None:
    from dataclasses import replace

    closed = replace(stressed.loans[0], status="closed")
    mutated = replace(stressed, loans=[closed, *stressed.loans[1:]])
    delta = Decimal(stressed.loans[0].principal)
    assert (
        sum(M.direct_vector(mutated).values(), Decimal(0))
        == sum(M.direct_vector(stressed).values(), Decimal(0)) - delta
    )
