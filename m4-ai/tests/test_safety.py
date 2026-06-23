"""The SPARQL safety gate: read-only, known schema only."""

from __future__ import annotations

import pytest
from lens_m4.safety import is_safe

_SELECT = (
    "PREFIX lens: <https://lens.example/ontology/> SELECT ?s WHERE { ?s lens:borrower ?b } LIMIT 5"
)


def test_select_is_safe() -> None:
    assert is_safe(_SELECT).safe


def test_ask_is_safe() -> None:
    q = "PREFIX lens: <https://lens.example/ontology/> ASK { ?s lens:borrower ?b }"
    assert is_safe(q).safe


@pytest.mark.parametrize(
    "bad",
    [
        "DELETE WHERE { ?s ?p ?o }",
        "INSERT DATA { <https://lens.example/id/X> a <https://lens.example/ontology/Limit> }",
        "PREFIX lens: <https://lens.example/ontology/> "
        "SELECT ?x WHERE { SERVICE <http://evil/> { ?x ?p ?o } }",
        "DROP ALL",
        "CLEAR DEFAULT",
    ],
)
def test_mutations_and_federation_rejected(bad: str) -> None:
    assert not is_safe(bad).safe


def test_unknown_namespace_rejected() -> None:
    q = "SELECT ?s WHERE { ?s <http://evil.example/p> ?o }"
    assert not is_safe(q).safe


def test_construct_rejected() -> None:
    q = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
    assert not is_safe(q).safe
