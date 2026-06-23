"""RDF store abstraction: query + SPARQL Update, plus a graph snapshot.

Two backends behind one interface so the action logic is identical in tests
(in-memory rdflib) and at runtime (Fuseki over HTTP):

* :class:`InMemoryStore` — an rdflib graph; used by the unit tests.
* :class:`FusekiStore` — the live triplestore the app writes to.
"""

from __future__ import annotations

from typing import Protocol

import requests
from rdflib import Graph
from rdflib.query import Result

_TIMEOUT = 60


class StoreError(RuntimeError):
    """Raised when the store cannot be reached or rejects a request."""


class Store(Protocol):
    """Minimal read/write interface used by the action layer."""

    def select(self, query: str) -> list[dict[str, str | None]]: ...

    def update(self, sparql_update: str) -> None: ...

    def snapshot(self) -> Graph:
        """Return the full current graph (for SHACL validation)."""
        ...


def _rows_from_result(result: Result) -> list[dict[str, str | None]]:
    variables = list(result.vars or [])
    rows: list[dict[str, str | None]] = []
    for binding in result.bindings:
        rows.append(
            {str(v): (None if binding.get(v) is None else str(binding.get(v))) for v in variables}
        )
    return rows


class InMemoryStore:
    """An in-memory rdflib-backed store (used in tests)."""

    def __init__(self, graph: Graph | None = None) -> None:
        self._graph = graph if graph is not None else Graph()

    def select(self, query: str) -> list[dict[str, str | None]]:
        return _rows_from_result(self._graph.query(query))

    def update(self, sparql_update: str) -> None:
        self._graph.update(sparql_update)

    def snapshot(self) -> Graph:
        # Return an independent copy so callers can build candidate graphs
        # without mutating the live store.
        copy = Graph()
        copy += self._graph
        return copy


class FusekiStore:
    """A Fuseki-backed store over HTTP (used at runtime)."""

    def __init__(self, query_url: str, update_url: str, timeout: int = _TIMEOUT) -> None:
        self._query_url = query_url
        self._update_url = update_url
        self._timeout = timeout

    def select(self, query: str) -> list[dict[str, str | None]]:
        try:
            resp = requests.post(
                self._query_url,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise StoreError(f"query failed: {exc}") from exc
        if not resp.ok:
            raise StoreError(f"query failed: {resp.status_code} {resp.text[:200]}")
        payload = resp.json()
        variables: list[str] = payload.get("head", {}).get("vars", [])
        rows: list[dict[str, str | None]] = []
        for binding in payload.get("results", {}).get("bindings", []):
            rows.append({v: (binding.get(v) or {}).get("value") for v in variables})
        return rows

    def update(self, sparql_update: str) -> None:
        try:
            resp = requests.post(
                self._update_url,
                data={"update": sparql_update},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise StoreError(f"update failed: {exc}") from exc
        if not resp.ok:
            raise StoreError(f"update failed: {resp.status_code} {resp.text[:200]}")

    def snapshot(self) -> Graph:
        # Fetch the whole graph as Turtle for SHACL validation.
        try:
            resp = requests.post(
                self._query_url,
                data={"query": "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"},
                headers={"Accept": "text/turtle"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise StoreError(f"snapshot failed: {exc}") from exc
        g = Graph()
        g.parse(data=resp.text, format="turtle")
        return g
