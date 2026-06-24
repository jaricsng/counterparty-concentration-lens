"""FusekiStore surfaces failures as StoreError (no silent swallow).

The unit tests use the in-memory store; here we point a real FusekiStore at a
dead endpoint to confirm the HTTP error paths raise rather than return bad data.
"""

from __future__ import annotations

import pytest
from lens_m2.store import FusekiStore, StoreError
from rdflib import Graph

DEAD = "http://localhost:9"  # nothing listens on the discard port


def _store() -> FusekiStore:
    return FusekiStore(f"{DEAD}/query", f"{DEAD}/update")


def test_select_on_unreachable_server_raises() -> None:
    with pytest.raises(StoreError):
        _store().select("SELECT ?s WHERE { ?s ?p ?o }")


def test_update_on_unreachable_server_raises() -> None:
    with pytest.raises(StoreError):
        _store().update('INSERT DATA { <urn:a> <urn:b> "c" }')


def test_replace_on_unreachable_server_raises() -> None:
    g = Graph()
    g.parse(data='<urn:a> <urn:b> "c" .', format="nt")
    with pytest.raises(StoreError):
        _store().replace(g)
