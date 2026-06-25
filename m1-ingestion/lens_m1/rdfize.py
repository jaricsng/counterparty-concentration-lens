"""Map a :class:`DatasetSpec` to RDF triples (FIBO instances) for the Lens.

Produces exactly the vocabulary the M0 application ontology defines
(`m0-ontology/ontology/lens.ttl`), so the M0 concentration queries run unchanged
on generated data. Each subject also carries a ``dct:source`` lineage note
recording the source table it came from.
"""

from __future__ import annotations

from decimal import Decimal

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, XSD

from .spec import DatasetSpec

LENS = Namespace("https://lens.example/ontology/")
LENSID = Namespace("https://lens.example/id/")
CMNS_ORG = Namespace("https://www.omg.org/spec/Commons/Organizations/")
FIBO_LOAN = Namespace("https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansGeneral/Loans/")
FIBO_DBT = Namespace("https://spec.edmcouncil.org/fibo/ontology/FBC/DebtAndEquities/Debt/")
FIBO_GTY = Namespace("https://spec.edmcouncil.org/fibo/ontology/FBC/DebtAndEquities/Guaranty/")


def _iri(identifier: str) -> URIRef:
    return LENSID[identifier]


def _dec(value: int) -> Literal:
    return Literal(str(value), datatype=XSD.decimal)


def build_graph(spec: DatasetSpec) -> Graph:
    """Build an in-memory RDF graph of the dataset's FIBO instances."""
    g = Graph()
    g.bind("lens", LENS)
    g.bind("lensid", LENSID)
    g.bind("cmns-org", CMNS_ORG)
    g.bind("fibo-loan", FIBO_LOAN)
    g.bind("fibo-dbt", FIBO_DBT)
    g.bind("fibo-gty", FIBO_GTY)
    g.bind("dct", DCTERMS)

    for e in spec.entities:
        s = _iri(e.entity_id)
        g.add((s, RDF.type, CMNS_ORG.LegalEntity))
        g.add((s, RDFS.label, Literal(e.name)))
        g.add((s, LENS.sector, Literal(e.sector)))
        g.add((s, LENS.counterpartyType, Literal(e.counterparty_type)))
        g.add((s, LENS.status, Literal("active")))
        g.add((s, DCTERMS.source, Literal("entities.csv")))
        if e.parent_id:
            g.add((s, LENS.isSubsidiaryOf, _iri(e.parent_id)))
        if e.eligible_capital is not None:
            g.add((s, LENS.eligibleCapital, _dec(e.eligible_capital)))
        if e.annual_revenue is not None:
            g.add((s, LENS.annualRevenue, _dec(e.annual_revenue)))
        if e.country:
            g.add((s, LENS.country, Literal(e.country)))
        if e.rating:
            g.add((s, LENS.rating, Literal(e.rating)))

    for ln in spec.loans:
        s = _iri(ln.loan_id)
        g.add((s, RDF.type, FIBO_LOAN.Loan))
        g.add((s, RDFS.label, Literal(f"Loan {ln.loan_id}")))
        g.add((s, LENS.lender, _iri(ln.lender_id)))
        g.add((s, LENS.borrower, _iri(ln.borrower_id)))
        g.add((s, LENS.principalAmount, _dec(ln.principal)))
        g.add((s, LENS.currency, Literal(ln.currency)))
        g.add((s, LENS.status, Literal(ln.status)))
        g.add((s, DCTERMS.source, Literal("loans.csv")))

    for gt in spec.guarantees:
        s = _iri(gt.guarantee_id)
        g.add((s, RDF.type, FIBO_GTY.Guaranty))
        g.add((s, RDFS.label, Literal(f"Guaranty {gt.guarantee_id}")))
        g.add((s, LENS.guarantor, _iri(gt.guarantor_id)))
        g.add((s, LENS.guaranteedLoan, _iri(gt.guaranteed_loan_id)))
        g.add((s, LENS.guaranteedAmount, _dec(gt.amount)))
        g.add((s, LENS.currency, Literal(gt.currency)))
        # Status enables M2 soft-delete (deactivate a guaranty -> drops exposure).
        g.add((s, LENS.status, Literal("active")))
        g.add((s, DCTERMS.source, Literal("guarantees.csv")))

    for col in spec.collateral:
        s = _iri(col.collateral_id)
        g.add((s, RDF.type, FIBO_DBT.Collateral))
        g.add((s, RDFS.label, Literal(col.description)))
        g.add((s, LENS.pledgedBy, _iri(col.pledged_by_id)))
        for loan_id in col.secures_loan_ids:
            g.add((s, LENS.securesLoan, _iri(loan_id)))
        if col.issuer_id:
            g.add((s, LENS.collateralIssuer, _iri(col.issuer_id)))
        if col.collateral_value is not None:
            g.add((s, LENS.collateralValue, _dec(col.collateral_value)))
            haircut = Decimal(col.haircut_pct) / 100
            g.add((s, LENS.haircut, Literal(str(haircut), datatype=XSD.decimal)))
        g.add((s, LENS.status, Literal("active")))
        g.add((s, DCTERMS.source, Literal("collateral.csv")))

    for lim in spec.limits:
        s = _iri(lim.limit_id)
        g.add((s, RDF.type, LENS.Limit))
        g.add((s, RDFS.label, Literal(f"Limit {lim.limit_id}")))
        g.add((s, LENS.limitAmount, _dec(lim.limit_amount)))
        g.add((s, LENS.currency, Literal(lim.currency)))
        g.add((s, LENS.status, Literal("active")))
        g.add((_iri(lim.entity_id), LENS.hasLimit, s))
        g.add((s, DCTERMS.source, Literal("limits.csv")))

    return g
