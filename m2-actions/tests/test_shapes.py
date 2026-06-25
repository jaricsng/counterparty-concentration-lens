"""Per-shape SHACL coverage: each business rule, accepted AND rejected.

The action tests prove the guard end-to-end; these pin each shape so a change to
one rule (or its message) is caught directly. A small valid base graph (two
entities + a loan) gives the class/existence constraints something to resolve.
"""

from __future__ import annotations

from lens_m2 import graphbuild as G
from lens_m2.config import SHAPES_PATH
from lens_m2.graphbuild import CMNS_ORG, LENS, iri
from lens_m2.validation import validate
from rdflib import Graph, Literal
from rdflib.namespace import RDF, XSD


def _base() -> Graph:
    g = Graph()
    g += G.entity_graph("LE-A", "Acme A", "corporate", "tech")
    g += G.entity_graph("LE-B", "Acme B", "bank", "financials")
    g += G.loan_graph("LN-1", "LE-B", "LE-A", 1000)
    return g


def _check(graph: Graph):
    return validate(graph, SHAPES_PATH)


def test_base_graph_conforms() -> None:
    assert _check(_base()).conforms


# --- LegalEntityShape ---------------------------------------------------- #


def test_entity_counterparty_type_enum() -> None:
    good = _base() + G.entity_graph("LE-C", "C Co", "nbfi", "funds")
    assert _check(good).conforms

    bad = _base() + G.entity_graph("LE-C", "C Co", "alien", "funds")
    res = _check(bad)
    assert not res.conforms
    assert any("counterpartyType must be one of" in m for m in res.messages)


def test_entity_requires_sector() -> None:
    g = _base()
    s = iri("LE-C")
    g.add((s, RDF.type, CMNS_ORG.LegalEntity))
    g.add((s, LENS.counterpartyType, Literal("bank")))  # but no sector
    res = _check(g)
    assert not res.conforms
    assert any("needs a sector" in m for m in res.messages)


# --- LoanShape ----------------------------------------------------------- #


def test_loan_principal_must_be_positive() -> None:
    bad = _base() + G.loan_graph("LN-2", "LE-B", "LE-A", -5)
    res = _check(bad)
    assert not res.conforms
    assert any("principalAmount must be a positive decimal" in m for m in res.messages)


def test_loan_borrower_must_exist() -> None:
    bad = _base() + G.loan_graph("LN-3", "LE-B", "LE-MISSING", 1000)
    res = _check(bad)
    assert not res.conforms
    assert any("existing borrower" in m for m in res.messages)


# --- GuarantyShape (existence + two-distinct-entities) ------------------- #


def test_guaranty_distinct_from_borrower() -> None:
    # LE-B is the lender, so a guaranty by LE-B over LN-1 is two distinct parties
    ok = _base() + G.guaranty_graph("GTY-1", "LE-B", "LN-1", 500)
    assert _check(ok).conforms

    # LE-A IS the borrower of LN-1 -> self-guaranty, rejected
    bad = _base() + G.guaranty_graph("GTY-2", "LE-A", "LN-1", 500)
    res = _check(bad)
    assert not res.conforms
    assert any("must differ" in m for m in res.messages)


def test_guaranty_guarantor_must_exist() -> None:
    bad = _base() + G.guaranty_graph("GTY-3", "LE-NOPE", "LN-1", 500)
    res = _check(bad)
    assert not res.conforms
    assert any("existing guarantor" in m for m in res.messages)


# --- CollateralShape ----------------------------------------------------- #


def test_collateral_valid_and_dangling_refs() -> None:
    ok = _base() + G.collateral_graph("COL-1", "real_estate", "LE-A", ["LN-1"])
    assert _check(ok).conforms

    bad_pledger = _base() + G.collateral_graph("COL-2", "real_estate", "LE-NOPE", ["LN-1"])
    assert any("pledged by an existing" in m for m in _check(bad_pledger).messages)

    bad_loan = _base() + G.collateral_graph("COL-3", "real_estate", "LE-A", ["LN-NOPE"])
    assert any("secure at least one existing" in m for m in _check(bad_loan).messages)


# --- LimitShape ---------------------------------------------------------- #


def test_limit_amount_must_be_positive() -> None:
    assert _check(_base() + G.limit_graph("LIM-1", "LE-A", 1000)).conforms

    res = _check(_base() + G.limit_graph("LIM-2", "LE-A", -1))
    assert not res.conforms
    assert any("limitAmount must be a positive decimal" in m for m in res.messages)


# --- CollateralShape: credit-risk-mitigation bounds ---------------------- #


def test_collateral_value_and_haircut_bounds() -> None:
    def _col(value: str, haircut: str) -> Graph:
        g = _base() + G.collateral_graph("COL-1", "bond", "LE-A", ["LN-1"])
        c = iri("COL-1")
        g.add((c, LENS.collateralValue, Literal(value, datatype=XSD.decimal)))
        g.add((c, LENS.haircut, Literal(haircut, datatype=XSD.decimal)))
        return g

    assert _check(_col("1000", "0.2")).conforms
    assert any("haircut" in m for m in _check(_col("1000", "1.5")).messages)
    assert any("collateralValue" in m for m in _check(_col("-5", "0.2")).messages)
