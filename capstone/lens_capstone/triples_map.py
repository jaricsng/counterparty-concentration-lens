"""Pure row -> N-Triples mapping (the Spark job's transform, Spark-free).

Each function maps one CSV source row (a dict) to a list of N-Triples lines,
using the exact same FIBO vocabulary and literal forms as the M1 loader
(``lens_m1.rdfize``). Because it is a plain function with no Spark dependency, it
is unit-tested directly to prove the Spark job emits identical triples; the Spark
job just applies these functions across partitions.

Collateral that secures several loans is one row per (collateral, loan); the
repeated collateral-level triples collapse in the RDF set, so row-wise emission
is correct.
"""

from __future__ import annotations

from decimal import Decimal

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, XSD

LENS = Namespace("https://lens.example/ontology/")
LENSID = Namespace("https://lens.example/id/")
CMNS_ORG = Namespace("https://www.omg.org/spec/Commons/Organizations/")
FIBO_LOAN = Namespace("https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansGeneral/Loans/")
FIBO_DBT = Namespace("https://spec.edmcouncil.org/fibo/ontology/FBC/DebtAndEquities/Debt/")
FIBO_GTY = Namespace("https://spec.edmcouncil.org/fibo/ontology/FBC/DebtAndEquities/Guaranty/")


def _id(local: str) -> URIRef:
    return LENSID[local]


def _dec(value: str) -> Literal:
    return Literal(str(value), datatype=XSD.decimal)


def _nt(graph: Graph) -> list[str]:
    return [line for line in graph.serialize(format="nt").splitlines() if line.strip()]


def _opt(value: str | None) -> str | None:
    return value if value not in (None, "") else None


def entity_to_triples(row: dict[str, str]) -> list[str]:
    g = Graph()
    s = _id(row["entity_id"])
    g.add((s, RDF.type, CMNS_ORG.LegalEntity))
    g.add((s, RDFS.label, Literal(row["entity_name"])))
    g.add((s, LENS.sector, Literal(row["sector"])))
    g.add((s, LENS.counterpartyType, Literal(row["counterparty_type"])))
    g.add((s, LENS.status, Literal("active")))
    parent = _opt(row.get("parent_entity_id"))
    if parent:
        g.add((s, LENS.isSubsidiaryOf, _id(parent)))
    if _opt(row.get("eligible_capital")):
        g.add((s, LENS.eligibleCapital, _dec(row["eligible_capital"])))
    if _opt(row.get("annual_revenue")):
        g.add((s, LENS.annualRevenue, _dec(row["annual_revenue"])))
    if _opt(row.get("country")):
        g.add((s, LENS.country, Literal(row["country"])))
    if _opt(row.get("rating")):
        g.add((s, LENS.rating, Literal(row["rating"])))
    g.add((s, DCTERMS.source, Literal("entities.csv")))
    return _nt(g)


def loan_to_triples(row: dict[str, str]) -> list[str]:
    g = Graph()
    s = _id(row["loan_id"])
    g.add((s, RDF.type, FIBO_LOAN.Loan))
    g.add((s, RDFS.label, Literal(f"Loan {row['loan_id']}")))
    g.add((s, LENS.lender, _id(row["lender_entity_id"])))
    g.add((s, LENS.borrower, _id(row["borrower_entity_id"])))
    g.add((s, LENS.principalAmount, _dec(row["exposure_amount"])))
    g.add((s, LENS.currency, Literal(row["currency"])))
    g.add((s, LENS.status, Literal(row["status"])))
    g.add((s, LENS.maturityYears, _dec(row.get("maturity_years") or "3")))
    g.add((s, DCTERMS.source, Literal("loans.csv")))
    return _nt(g)


def guarantee_to_triples(row: dict[str, str]) -> list[str]:
    g = Graph()
    s = _id(row["guarantee_id"])
    g.add((s, RDF.type, FIBO_GTY.Guaranty))
    g.add((s, RDFS.label, Literal(f"Guaranty {row['guarantee_id']}")))
    g.add((s, LENS.guarantor, _id(row["guarantor_entity_id"])))
    g.add((s, LENS.guaranteedLoan, _id(row["beneficiary_loan_id"])))
    g.add((s, LENS.guaranteedAmount, _dec(row["amount"])))
    g.add((s, LENS.currency, Literal(row["currency"])))
    g.add((s, LENS.status, Literal("active")))
    g.add((s, DCTERMS.source, Literal("guarantees.csv")))
    return _nt(g)


def collateral_to_triples(row: dict[str, str]) -> list[str]:
    g = Graph()
    s = _id(row["collateral_id"])
    g.add((s, RDF.type, FIBO_DBT.Collateral))
    g.add((s, RDFS.label, Literal(row["collateral_type"])))
    g.add((s, LENS.pledgedBy, _id(row["pledged_by_entity_id"])))
    g.add((s, LENS.securesLoan, _id(row["securing_loan_id"])))
    issuer = _opt(row.get("issuer_entity_id"))
    if issuer:
        g.add((s, LENS.collateralIssuer, _id(issuer)))
    value = _opt(row.get("collateral_value"))
    if value:
        g.add((s, LENS.collateralValue, _dec(value)))
        haircut = Decimal(int(row.get("haircut_pct") or 0)) / 100
        g.add((s, LENS.haircut, Literal(str(haircut), datatype=XSD.decimal)))
    g.add((s, LENS.status, Literal("active")))
    g.add((s, DCTERMS.source, Literal("collateral.csv")))
    return _nt(g)


def limit_to_triples(row: dict[str, str]) -> list[str]:
    g = Graph()
    s = _id(row["limit_id"])
    g.add((s, RDF.type, LENS.Limit))
    g.add((s, RDFS.label, Literal(f"Limit {row['limit_id']}")))
    g.add((s, LENS.limitAmount, _dec(row["single_name_limit"])))
    g.add((s, LENS.currency, Literal(row["currency"])))
    g.add((s, LENS.status, Literal("active")))
    g.add((_id(row["entity_id"]), LENS.hasLimit, s))
    g.add((s, DCTERMS.source, Literal("limits.csv")))
    return _nt(g)


# Table name -> (csv filename, mapping function). Used by the Spark job and tests.
TABLE_MAP = {
    "entities": ("entities.csv", entity_to_triples),
    "loans": ("loans.csv", loan_to_triples),
    "guarantees": ("guarantees.csv", guarantee_to_triples),
    "collateral": ("collateral.csv", collateral_to_triples),
    "limits": ("limits.csv", limit_to_triples),
}
