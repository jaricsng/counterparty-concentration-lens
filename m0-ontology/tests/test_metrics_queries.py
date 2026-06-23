"""The M0 concentration-metric SPARQL queries match the M1 Python oracle.

Builds an in-memory rdflib graph from the M1 synthetic datasets and checks each
``.rq`` against ``lens_m1.metrics`` on BOTH calm and stressed — so the SPARQL
and the reference implementation agree, and the engineered thresholds are
crossed only under stress.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# Make both module packages importable.
M0_ROOT = Path(__file__).resolve().parent.parent
M1_ROOT = M0_ROOT.parent / "m1-ingestion"
for _p in (M0_ROOT, str(M1_ROOT)):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lens_m0 import metrics_queries as Q  # noqa: E402
from lens_m0.config import load_settings  # noqa: E402
from lens_m0.graph import GraphRunner  # noqa: E402
from lens_m1 import datasets, rdfize  # noqa: E402
from lens_m1 import metrics as Oracle  # noqa: E402

QUERIES = load_settings().queries_dir


def _runner(variant: str) -> GraphRunner:
    return GraphRunner(rdfize.build_graph(datasets.get_dataset(variant)))


def _approx(a: Decimal, b: Decimal, tol: str = "0.0005") -> bool:
    return abs(a - b) < Decimal(tol)


# --- HHI / CR10 match the oracle, direct vs connected ------------------------ #


@pytest.mark.parametrize("variant", ["calm", "stressed"])
def test_hhi_matches_oracle(variant: str) -> None:
    spec = datasets.get_dataset(variant)
    got = Q.hhi(_runner(variant), QUERIES)
    assert _approx(got.direct, Oracle.hhi(Oracle.direct_vector(spec)))
    assert _approx(got.connected, Oracle.hhi(Oracle.attributed_vector(spec)))


@pytest.mark.parametrize("variant", ["calm", "stressed"])
def test_cr10_matches_oracle(variant: str) -> None:
    spec = datasets.get_dataset(variant)
    got = Q.cr10(_runner(variant), QUERIES)
    assert _approx(got.direct, Oracle.cr10(Oracle.direct_vector(spec)))
    assert _approx(got.connected, Oracle.cr10(Oracle.attributed_vector(spec)))


def test_stressed_hhi_cr10_breach_only_on_connected() -> None:
    got_hhi = Q.hhi(_runner("stressed"), QUERIES)
    got_cr10 = Q.cr10(_runner("stressed"), QUERIES)
    assert got_hhi.connected > Decimal("0.18") > got_hhi.direct
    assert got_cr10.connected > Decimal("0.60") > got_cr10.direct


def test_calm_hhi_within_band() -> None:
    assert Q.hhi(_runner("calm"), QUERIES).connected < Decimal("0.18")


# --- Risk-owner vector matches the oracle exactly ---------------------------- #


@pytest.mark.parametrize("variant", ["calm", "stressed"])
def test_connected_by_owner_matches_oracle(variant: str) -> None:
    spec = datasets.get_dataset(variant)
    got = Q.connected_by_owner(_runner(variant), QUERIES)
    oracle = Oracle.attributed_vector(spec)
    assert got == oracle


# --- Sector concentration ---------------------------------------------------- #


def test_sector_concentration_matches_oracle() -> None:
    spec = datasets.get_dataset("stressed")
    got = Q.sector_shares(_runner("stressed"), QUERIES)
    oracle = Oracle.sector_shares(spec)
    assert _approx(got["financial services"], oracle["financial services"])
    assert got["financial services"] > Decimal("0.30")  # breaches in stressed


def test_sector_calm_within_band() -> None:
    got = Q.sector_shares(_runner("calm"), QUERIES)
    assert max(got.values()) < Decimal("0.30")


# --- Structural wrong-way risk ---------------------------------------------- #


def test_wwr_stressed_flags_same_issuer() -> None:
    flags = Q.wrong_way_risk(_runner("stressed"), QUERIES)
    assert len(flags) == 1
    assert flags[0].loan == "LN-1030"
    assert flags[0].issuer == "LE-0010"
    assert flags[0].group == "LE-0010"


def test_wwr_calm_none() -> None:
    assert Q.wrong_way_risk(_runner("calm"), QUERIES) == []


# --- Watchlist bands --------------------------------------------------------- #


def test_watchlist_matches_oracle_bands() -> None:
    got = {r.entity: r.band for r in Q.watchlist(_runner("stressed"), QUERIES)}
    oracle = {u.name: u.band for u in Oracle.utilisations(datasets.get_dataset("stressed"))}
    assert got == oracle


def test_watchlist_stressed_has_reds_and_ambers() -> None:
    bands = [r.band for r in Q.watchlist(_runner("stressed"), QUERIES)]
    assert bands.count("red") == 3
    assert bands.count("amber") == 4


def test_watchlist_calm_all_green() -> None:
    assert all(r.band == "green" for r in Q.watchlist(_runner("calm"), QUERIES))


# --- UBO aggregation (§9.1): UBO breaches, no subsidiary does ----------------- #


def test_ubo_aggregation_breach_pattern() -> None:
    rows = Q.ubo_aggregation(_runner("stressed"), QUERIES, "https://lens.example/id/LE-0021")
    ubo = next(r for r in rows if r.is_ubo)
    subs = [r for r in rows if not r.is_ubo]
    assert ubo.member == "LE-0020"
    assert ubo.connected == Decimal("24000000")
    assert ubo.band == "red"  # UBO breaches
    assert subs and all(s.band != "red" for s in subs)  # no subsidiary breaches


# --- NBFI cascade (§3.5): direct small, cascade large ------------------------ #


def test_nbfi_cascade_dwarfs_direct() -> None:
    rows = Q.nbfi_cascade(_runner("stressed"), QUERIES, "https://lens.example/id/LE-0030")
    direct = sum((r.amount for r in rows if r.contribution_type.startswith("1")), Decimal(0))
    total = sum((r.amount for r in rows), Decimal(0))
    assert direct == Decimal("5000000")
    assert total == Decimal("47000000")  # matches oracle connected exposure
    assert total == Oracle.connected_exposure(datasets.get_dataset("stressed"), "LE-0030").total
