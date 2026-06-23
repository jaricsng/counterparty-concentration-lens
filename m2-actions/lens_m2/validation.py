"""SHACL validation of a candidate graph (data-quality rules as code).

A write is validated by building the *candidate* graph — the current store
snapshot plus the proposed triples — and checking it conforms to the shapes.
Validating the full candidate graph means referential rules (a loan's borrower
must exist) and cross-node rules (a guaranty's two parties must differ) are
checked against real data, not just the new node in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pyshacl import validate as shacl_validate
from rdflib import Graph


@dataclass(frozen=True)
class ValidationResult:
    conforms: bool
    messages: list[str]

    @property
    def reason(self) -> str:
        return "; ".join(self.messages) if self.messages else "ok"


@lru_cache(maxsize=4)
def _load_shapes(shapes_path: str) -> Graph:
    g = Graph()
    g.parse(shapes_path, format="turtle")
    return g


def _extract_messages(report_graph: Graph) -> list[str]:
    from rdflib.namespace import SH

    messages = [str(m) for m in report_graph.objects(predicate=SH.resultMessage)]
    return sorted(set(messages))


def validate(candidate: Graph, shapes_path: Path) -> ValidationResult:
    """Validate the candidate graph against the SHACL shapes."""
    shapes = _load_shapes(str(shapes_path))
    conforms, report_graph, _ = shacl_validate(
        candidate,
        shacl_graph=shapes,
        advanced=True,  # enable SHACL-SPARQL constraints
        inference="none",
        meta_shacl=False,
    )
    messages = [] if conforms else _extract_messages(report_graph)
    return ValidationResult(conforms=conforms, messages=messages)
