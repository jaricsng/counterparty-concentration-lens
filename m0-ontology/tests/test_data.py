"""The synthetic instance data is well-formed and within the M0 size brief."""

from __future__ import annotations

from lens_m0.config import Settings
from rdflib import RDF, Graph, Namespace, URIRef

CMNS_ORG = Namespace("https://www.omg.org/spec/Commons/Organizations/")
LENS = Namespace("https://lens.example/ontology/")
FIBO_LOAN = URIRef("https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansGeneral/Loans/Loan")


def _graph(settings: Settings) -> Graph:
    g = Graph()
    g.parse(settings.instances_path, format="turtle")
    return g


def test_data_parses(settings: Settings) -> None:
    assert len(_graph(settings)) > 0


def test_entity_count_in_brief(settings: Settings) -> None:
    g = _graph(settings)
    entities = set(g.subjects(RDF.type, CMNS_ORG.LegalEntity))
    # CLAUDE.md M0 brief: ~15-25 legal entities.
    assert 15 <= len(entities) <= 25, f"expected 15-25 entities, got {len(entities)}"


def test_every_loan_has_borrower_lender_amount(settings: Settings) -> None:
    g = _graph(settings)
    loans = list(g.subjects(RDF.type, FIBO_LOAN))
    assert loans, "no loans found"
    for loan in loans:
        assert (loan, LENS.borrower, None) in g, f"{loan} has no borrower"
        assert (loan, LENS.lender, None) in g, f"{loan} has no lender"
        assert next(g.objects(loan, LENS.principalAmount), None) is not None


def test_shared_collateral_exists(settings: Settings) -> None:
    """At least one collateral item must secure >1 loan (the hidden link)."""
    g = _graph(settings)
    shared = [
        col
        for col in set(g.subjects(LENS.securesLoan, None))
        if len(list(g.objects(col, LENS.securesLoan))) > 1
    ]
    assert shared, "expected at least one shared (cross-pledged) collateral item"
