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
    return set_values(query, "head", head_iri)


def set_values(query: str, var: str, iri: str) -> str:
    """Bind a ``VALUES ?<var> { ... }`` clause to a single IRI.

    Lets the metric queries be parameterised by a counterparty / NBFI without
    editing the query text.

    Raises:
        ValueError: if the query has no ``VALUES ?<var> { ... }`` clause.
    """
    pattern = re.compile(r"VALUES\s+\?" + re.escape(var) + r"\s*\{[^}]*\}")
    new_query, count = pattern.subn(f"VALUES ?{var} {{ <{iri}> }}", query)
    if count == 0:
        raise ValueError(f"query has no `VALUES ?{var} {{ ... }}` clause to parameterise")
    return new_query
