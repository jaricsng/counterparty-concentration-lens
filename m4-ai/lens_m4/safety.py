"""Validate that a (possibly LLM-generated) SPARQL query is safe to execute.

Hard rule (CLAUDE.md): never run unverified generated SPARQL. A query is only
allowed if it is a **read-only** SELECT/ASK, contains no update or federation
keywords, and references only the project's known namespaces. Anything else is
rejected before it can touch the store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rdflib.plugins.sparql import prepareQuery

# Update / federation / data-loading keywords that must never appear.
_FORBIDDEN = (
    "INSERT",
    "DELETE",
    "LOAD",
    "CLEAR",
    "DROP",
    "CREATE",
    "ADD",
    "MOVE",
    "COPY",
    "WITH",
    "SERVICE",
)
_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(_FORBIDDEN) + r")\b", re.IGNORECASE)

# Namespaces the query is allowed to reference (the known schema).
_ALLOWED_NS = (
    "https://lens.example/",
    "https://www.omg.org/spec/Commons/",
    "https://spec.edmcouncil.org/fibo/",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2001/XMLSchema#",
    "http://purl.org/dc/terms/",
)
_IRI_RE = re.compile(r"<(http[^>]+)>")
_READ_FORMS = {"SelectQuery", "AskQuery"}


@dataclass(frozen=True)
class SafetyResult:
    safe: bool
    reason: str


def is_safe(query: str) -> SafetyResult:
    """Return whether ``query`` is a read-only query over the known schema."""
    match = _FORBIDDEN_RE.search(query)
    if match:
        return SafetyResult(False, f"forbidden keyword '{match.group(1).upper()}'")

    for iri in _IRI_RE.findall(query):
        if not any(iri.startswith(ns) for ns in _ALLOWED_NS):
            return SafetyResult(False, f"IRI outside the known schema: {iri}")

    try:
        prepared = prepareQuery(query)  # raises on SPARQL Update or syntax errors
    except Exception as exc:  # noqa: BLE001 - any parse failure is unsafe
        return SafetyResult(False, f"unparseable or not a query: {str(exc)[:120]}")

    form = getattr(prepared.algebra, "name", "")
    if form not in _READ_FORMS:
        return SafetyResult(False, f"not a read-only SELECT/ASK (was {form or 'unknown'})")

    return SafetyResult(True, "ok")
