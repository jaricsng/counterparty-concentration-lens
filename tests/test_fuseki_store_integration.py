"""FusekiStore round-trips over real HTTP — the path unit tests stub out.

Exercises the SPARQL serialization the store builds (N-Triples / INSERT DATA /
DROP DEFAULT) and the JSON result parsing, against a live triplestore.
"""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal, Namespace

pytestmark = pytest.mark.integration

ID = Namespace("https://lens.example/id/")
LENS = Namespace("https://lens.example/ontology/")


def test_replace_then_select_and_snapshot(fuseki_store):
    g = Graph()
    g.add((ID["TS-1"], LENS.status, Literal("active")))
    g.add((ID["TS-1"], LENS.note, Literal("hello")))
    fuseki_store.replace(g)  # DROP DEFAULT + INSERT DATA over HTTP

    rows = fuseki_store.select(
        "SELECT ?o WHERE { <https://lens.example/id/TS-1> "
        "<https://lens.example/ontology/status> ?o }"
    )
    assert [r["o"] for r in rows] == ["active"]

    snap = fuseki_store.snapshot()
    assert (ID["TS-1"], LENS.status, Literal("active")) in snap
    assert len(snap) == 2


def test_update_insert_then_delete(fuseki_store):
    fuseki_store.replace(Graph())  # empty the default graph
    assert fuseki_store.select("SELECT ?s WHERE { ?s ?p ?o }") == []

    fuseki_store.update(
        "INSERT DATA { <https://lens.example/id/TS-2> "
        '<https://lens.example/ontology/status> "active" }'
    )
    assert fuseki_store.select("SELECT ?s WHERE { ?s ?p ?o }")

    fuseki_store.update("DELETE WHERE { <https://lens.example/id/TS-2> ?p ?o }")
    assert fuseki_store.select("SELECT ?o WHERE { <https://lens.example/id/TS-2> ?p ?o }") == []
