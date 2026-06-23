"""Load the SPARQL query files and parameterise them by counterparty group.

The ``.rq`` files carry a literal ``VALUES ?head { lensid:LE-0001 }`` line so
they run unchanged in the Fuseki UI. :func:`set_group_head` swaps that for any
group head IRI without touching the rest of the query.
"""

from __future__ import annotations

import re
from pathlib import Path

# Matches `VALUES ?head { <anything> }` (single line), capturing nothing useful;
# we just replace the whole construct.
_VALUES_HEAD_RE = re.compile(r"VALUES\s+\?head\s*\{[^}]*\}")


def load_query(queries_dir: Path, name: str) -> str:
    """Read a named query file (with or without the ``.rq`` suffix)."""
    filename = name if name.endswith(".rq") else f"{name}.rq"
    return (queries_dir / filename).read_text(encoding="utf-8")


def set_group_head(query: str, head_iri: str) -> str:
    """Return ``query`` with every ``VALUES ?head { ... }`` bound to ``head_iri``.

    Raises:
        ValueError: if the query has no ``VALUES ?head { ... }`` to substitute.
    """
    replacement = f"VALUES ?head {{ <{head_iri}> }}"
    new_query, count = _VALUES_HEAD_RE.subn(replacement, query)
    if count == 0:
        raise ValueError("query has no `VALUES ?head { ... }` clause to parameterise")
    return new_query
