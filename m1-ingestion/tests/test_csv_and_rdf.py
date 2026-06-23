"""CSV round-trip and RDF mapping fidelity."""

from __future__ import annotations

from pathlib import Path

from lens_m1 import metrics as M
from lens_m1.csv_tables import read_dataset, write_dataset
from lens_m1.rdfize import build_graph
from lens_m1.spec import DatasetSpec
from rdflib import Namespace, URIRef
from rdflib.namespace import RDF

LENS = Namespace("https://lens.example/ontology/")
LENSID = Namespace("https://lens.example/id/")
FIBO_LOAN = URIRef("https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansGeneral/Loans/Loan")


def test_csv_roundtrip_preserves_data(stressed: DatasetSpec, tmp_path: Path) -> None:
    write_dataset(stressed, tmp_path)
    restored = read_dataset(tmp_path, "stressed")
    assert {e.entity_id for e in restored.entities} == {e.entity_id for e in stressed.entities}
    assert {ln.loan_id for ln in restored.loans} == {ln.loan_id for ln in stressed.loans}
    # Metrics computed on the round-tripped spec must match the original.
    assert M.attributed_vector(restored) == M.attributed_vector(stressed)
    assert len(M.wrong_way_risk_flags(restored)) == len(M.wrong_way_risk_flags(stressed))


def test_shared_collateral_survives_roundtrip(stressed: DatasetSpec, tmp_path: Path) -> None:
    write_dataset(stressed, tmp_path)
    restored = read_dataset(tmp_path, "stressed")
    shared = [c for c in restored.collateral if len(c.secures_loan_ids) > 1]
    assert shared, "shared collateral should survive the one-row-per-loan CSV form"


def test_rdf_uses_lens_vocabulary(stressed: DatasetSpec) -> None:
    g = build_graph(stressed)
    # Loans typed as FIBO loans, with borrower + principal in the lens vocab.
    loans = list(g.subjects(RDF.type, FIBO_LOAN))
    assert loans
    sample = LENSID["LN-1001"]
    assert (sample, LENS.borrower, LENSID["LE-0002"]) in g
    assert next(g.objects(sample, LENS.principalAmount), None) is not None
    # WWR collateral carries the issuer link.
    assert (LENSID["COL-3002"], LENS.collateralIssuer, LENSID["LE-0010"]) in g


def test_triple_count_scales_with_rows(stressed: DatasetSpec) -> None:
    g = build_graph(stressed)
    # Every loan contributes a fixed set of triples; sanity-check the order.
    assert len(g) > len(stressed.loans) * 5
