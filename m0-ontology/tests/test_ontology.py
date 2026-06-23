"""The application ontology parses and declares the terms the demo relies on."""

from __future__ import annotations

from lens_m0.config import Settings
from rdflib import OWL, RDF, Graph, URIRef

LENS = "https://lens.example/ontology/"


def test_ontology_parses(settings: Settings) -> None:
    graph = Graph()
    graph.parse(settings.ontology_path, format="turtle")
    assert len(graph) > 0


def test_imports_fibo(settings: Settings) -> None:
    graph = Graph()
    graph.parse(settings.ontology_path, format="turtle")
    imports = set(graph.objects(predicate=OWL.imports))
    assert any("edmcouncil.org/fibo" in str(i) for i in imports), "ontology must import FIBO"


def test_convenience_classes_present(settings: Settings) -> None:
    graph = Graph()
    graph.parse(settings.ontology_path, format="turtle")
    for cls in ("Exposure", "Limit"):
        assert (URIRef(LENS + cls), RDF.type, OWL.Class) in graph


def test_role_shortcut_properties_present(settings: Settings) -> None:
    graph = Graph()
    graph.parse(settings.ontology_path, format="turtle")
    expected = {
        "borrower",
        "lender",
        "guarantor",
        "guaranteedLoan",
        "guaranteedAmount",
        "pledgedBy",
        "securesLoan",
        "isSubsidiaryOf",
        "principalAmount",
        "limitAmount",
    }
    declared = {str(s).removeprefix(LENS) for s in graph.subjects() if str(s).startswith(LENS)}
    missing = expected - declared
    assert not missing, f"ontology is missing terms: {sorted(missing)}"
