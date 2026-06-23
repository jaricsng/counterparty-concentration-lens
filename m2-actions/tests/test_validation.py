"""SHACL shapes accept the base data and reject structural violations."""

from __future__ import annotations

from lens_m2.config import SHAPES_PATH
from lens_m2.store import InMemoryStore
from lens_m2.validation import validate
from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

LENS = Namespace("https://lens.example/ontology/")
LENSID = Namespace("https://lens.example/id/")
FIBO_LOAN = URIRef("https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansGeneral/Loans/Loan")


def test_base_data_conforms(store: InMemoryStore) -> None:
    assert validate(store.snapshot(), SHAPES_PATH).conforms


def test_loan_without_borrower_violates(store: InMemoryStore) -> None:
    g = store.snapshot()
    bad = LENSID["LN-BAD"]
    g.add((bad, RDF.type, FIBO_LOAN))
    g.add((bad, LENS.lender, LENSID["LE-0099"]))
    g.add((bad, LENS.principalAmount, Literal("100", datatype=XSD.decimal)))
    g.add((bad, LENS.status, Literal("active")))
    result = validate(g, SHAPES_PATH)
    assert not result.conforms
    assert "borrower" in result.reason.lower()


def test_negative_amount_violates(store: InMemoryStore) -> None:
    g = store.snapshot()
    bad = LENSID["LN-BAD"]
    g.add((bad, RDF.type, FIBO_LOAN))
    g.add((bad, LENS.lender, LENSID["LE-0099"]))
    g.add((bad, LENS.borrower, LENSID["LE-0041"]))
    g.add((bad, LENS.principalAmount, Literal("-100", datatype=XSD.decimal)))
    g.add((bad, LENS.status, Literal("active")))
    assert not validate(g, SHAPES_PATH).conforms
