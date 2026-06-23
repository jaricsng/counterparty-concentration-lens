"""Build the proposed RDF triples for a new object.

One source of triples per object, used twice: added to the candidate graph for
SHACL validation, and serialised into a SPARQL ``INSERT DATA`` for the write.
The vocabulary matches the M0 application ontology exactly.
"""

from __future__ import annotations

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

LENS = Namespace("https://lens.example/ontology/")
LENSID = Namespace("https://lens.example/id/")
CMNS_ORG = Namespace("https://www.omg.org/spec/Commons/Organizations/")
FIBO_LOAN = Namespace("https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansGeneral/Loans/")
FIBO_DBT = Namespace("https://spec.edmcouncil.org/fibo/ontology/FBC/DebtAndEquities/Debt/")
FIBO_GTY = Namespace("https://spec.edmcouncil.org/fibo/ontology/FBC/DebtAndEquities/Guaranty/")


def iri(local: str) -> URIRef:
    """Resolve a bare id (``LE-0001``) or a full IRI to a URIRef."""
    return URIRef(local) if local.startswith("http") else LENSID[local]


def _dec(value: float | int | str) -> Literal:
    return Literal(str(value), datatype=XSD.decimal)


def entity_graph(
    entity_id: str,
    name: str,
    counterparty_type: str,
    sector: str,
    parent_id: str | None = None,
    eligible_capital: int | None = None,
    annual_revenue: int | None = None,
) -> Graph:
    g, s = Graph(), iri(entity_id)
    g.add((s, RDF.type, CMNS_ORG.LegalEntity))
    g.add((s, RDFS.label, Literal(name)))
    g.add((s, LENS.counterpartyType, Literal(counterparty_type)))
    g.add((s, LENS.sector, Literal(sector)))
    g.add((s, LENS.status, Literal("active")))
    if parent_id:
        g.add((s, LENS.isSubsidiaryOf, iri(parent_id)))
    if eligible_capital is not None:
        g.add((s, LENS.eligibleCapital, _dec(eligible_capital)))
    if annual_revenue is not None:
        g.add((s, LENS.annualRevenue, _dec(annual_revenue)))
    return g


def loan_graph(
    loan_id: str, lender_id: str, borrower_id: str, principal: int, currency: str = "SGD"
) -> Graph:
    g, s = Graph(), iri(loan_id)
    g.add((s, RDF.type, FIBO_LOAN.Loan))
    g.add((s, RDFS.label, Literal(f"Loan {loan_id}")))
    g.add((s, LENS.lender, iri(lender_id)))
    g.add((s, LENS.borrower, iri(borrower_id)))
    g.add((s, LENS.principalAmount, _dec(principal)))
    g.add((s, LENS.currency, Literal(currency)))
    g.add((s, LENS.status, Literal("active")))
    return g


def guaranty_graph(
    guarantee_id: str,
    guarantor_id: str,
    guaranteed_loan_id: str,
    amount: int,
    currency: str = "SGD",
) -> Graph:
    g, s = Graph(), iri(guarantee_id)
    g.add((s, RDF.type, FIBO_GTY.Guaranty))
    g.add((s, RDFS.label, Literal(f"Guaranty {guarantee_id}")))
    g.add((s, LENS.guarantor, iri(guarantor_id)))
    g.add((s, LENS.guaranteedLoan, iri(guaranteed_loan_id)))
    g.add((s, LENS.guaranteedAmount, _dec(amount)))
    g.add((s, LENS.currency, Literal(currency)))
    g.add((s, LENS.status, Literal("active")))
    return g


def collateral_graph(
    collateral_id: str,
    description: str,
    pledged_by_id: str,
    secures_loan_ids: list[str],
    issuer_id: str | None = None,
) -> Graph:
    g, s = Graph(), iri(collateral_id)
    g.add((s, RDF.type, FIBO_DBT.Collateral))
    g.add((s, RDFS.label, Literal(description)))
    g.add((s, LENS.pledgedBy, iri(pledged_by_id)))
    for loan_id in secures_loan_ids:
        g.add((s, LENS.securesLoan, iri(loan_id)))
    if issuer_id:
        g.add((s, LENS.collateralIssuer, iri(issuer_id)))
    g.add((s, LENS.status, Literal("active")))
    return g


def limit_graph(limit_id: str, entity_id: str, limit_amount: int, currency: str = "SGD") -> Graph:
    g, s = Graph(), iri(limit_id)
    g.add((s, RDF.type, LENS.Limit))
    g.add((s, RDFS.label, Literal(f"Limit {limit_id}")))
    g.add((s, LENS.limitAmount, _dec(limit_amount)))
    g.add((s, LENS.currency, Literal(currency)))
    g.add((s, LENS.status, Literal("active")))
    g.add((iri(entity_id), LENS.hasLimit, s))
    return g


def insert_data(graph: Graph) -> str:
    """Serialise a proposed graph as a SPARQL ``INSERT DATA`` request."""
    triples = graph.serialize(format="nt")
    return f"INSERT DATA {{\n{triples}}}"
