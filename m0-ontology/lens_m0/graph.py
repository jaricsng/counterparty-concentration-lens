"""In-memory RDF backend (rdflib).

Used for fast unit tests and as the reference implementation of the
concentration logic. The same SPARQL query files run here and against Fuseki,
so the in-memory result is the oracle for the integration test.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import Graph
from rdflib.query import Result


class GraphRunner:
    """A :class:`~lens_m0.concentration.QueryRunner` backed by an rdflib graph."""

    def __init__(self, graph: Graph) -> None:
        self._graph = graph

    @property
    def graph(self) -> Graph:
        return self._graph

    def select(self, query: str) -> list[dict[str, str | None]]:
        """Run a SELECT query and return rows as stringified bindings.

        Stringifying gives one interface shared with the Fuseki JSON backend;
        numeric callers re-parse the values they need (e.g. as ``Decimal``).
        """
        result: Result = self._graph.query(query)
        variables = list(result.vars or [])
        rows: list[dict[str, str | None]] = []
        for binding in result.bindings:
            row_dict: dict[str, str | None] = {}
            for var in variables:
                value = binding.get(var)
                row_dict[str(var)] = None if value is None else str(value)
            rows.append(row_dict)
        return rows


def load_graph(*ttl_paths: Path, include_fibo: Path | None = None) -> Graph:
    """Parse the given Turtle files into a single in-memory graph.

    Args:
        ttl_paths: application ontology / instance files to load.
        include_fibo: optional FIBO Turtle file to also load. Loading FIBO is
            not required for the concentration query (it traverses instance
            triples), so unit tests skip it for speed.
    """
    graph = Graph()
    if include_fibo is not None:
        graph.parse(include_fibo, format="turtle")
    for path in ttl_paths:
        graph.parse(path, format="turtle")
    return graph
