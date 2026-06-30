"""Read-side view-model for the app — pure functions over a SPARQL runner.

Wires the M0 metric queries with the M3 role scope, returning plain dicts/lists
the UI renders. Kept free of Streamlit so it is unit-testable with an in-memory
runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from lens_m0 import concentration as C
from lens_m0 import metrics_queries as Q
from lens_m0.concentration import QueryRunner

_PREFIX = (
    "PREFIX lens: <https://lens.example/ontology/>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
)


def _local(iri: str | None) -> str:
    return iri.rsplit("/", 1)[-1] if iri else ""


def member_to_head(runner: QueryRunner) -> dict[str, str]:
    """Map every entity to its ultimate-parent group head."""
    rows = runner.select(
        _PREFIX + "SELECT ?e ?head WHERE { ?e lens:isSubsidiaryOf* ?head . "
        "FILTER NOT EXISTS { ?head lens:isSubsidiaryOf ?p } }"
    )
    return {_local(r["e"]): _local(r["head"]) for r in rows}


def group_heads(runner: QueryRunner) -> list[tuple[str, str]]:
    """All counterparty group heads (id, label), excluding the lender bank."""
    rows = runner.select(
        _PREFIX + "SELECT ?e ?name WHERE { ?e a <https://www.omg.org/spec/Commons/Organizations/"
        "LegalEntity> . OPTIONAL { ?e rdfs:label ?name } "
        "FILTER NOT EXISTS { ?e lens:isSubsidiaryOf ?p } "
        "FILTER NOT EXISTS { ?l lens:lender ?e } } ORDER BY ?e"
    )
    # rdfs: prefix needed
    return [(_local(r["e"]), r.get("name") or _local(r["e"])) for r in rows]


def label_index(runner: QueryRunner) -> dict[str, str]:
    """Lowercased group keyword -> head id, for the NL box."""
    index: dict[str, str] = {}
    for head, name in group_heads(runner):
        index[name.lower()] = head
        index[name.split()[0].lower()] = head  # first word, e.g. "acme"
    return index


# --- Conversational follow-up resolution (used by the M5 NL chat) ----------- #

# A group-bearing intent + how to re-ask it for a different group, so a bare
# "what about Vortex?" reuses the previous intent with the new entity.
_INTENT_REPHRASE: dict[str, str] = {
    "exposure_to_group": "exposure to {g}",
    "guarantee_chains": "guarantee chains touching {g}",
}


def resolve_followup(
    question: str, last_group: str | None, label_index: dict[str, str]
) -> tuple[str, str | None]:
    """Resolve a chat follow-up against the last-named group.

    Returns ``(effective_question, group_keyword_or_None)``. If the question names a
    known group it is used as-is; otherwise the last group is appended so a group-less
    follow-up (e.g. "show guarantee chains", "its exposure") stays on the same name.
    """
    ql = question.lower()
    mentioned = next((k for k in sorted(label_index, key=len, reverse=True) if k and k in ql), None)
    if mentioned:
        return question, mentioned
    if last_group:
        return f"{question} {last_group}", None
    return question, None


def rephrase_for_intent(intent: str | None, group_keyword: str | None) -> str | None:
    """Re-ask a group-bearing intent for a (possibly new) group; None if not applicable."""
    template = _INTENT_REPHRASE.get(intent or "")
    return template.format(g=group_keyword) if template and group_keyword else None


# Starter-prompt palette for the chat — example questions grouped by CCR area.
NL_PALETTE: list[tuple[str, list[str]]] = [
    (
        "Concentration",
        [
            "What is our total exposure to the Acme group?",
            "Top counterparties?",
            "Which names are within 75% of their limit?",
        ],
    ),
    (
        "Country / rating",
        ["Which country are we most exposed to?", "What is our rating concentration?"],
    ),
    (
        "Loss & capital",
        [
            "What is our total expected loss?",
            "How much regulatory capital do we need?",
            "What is our IFRS-9 ECL?",
        ],
    ),
    (
        "Forward-looking",
        [
            "What is our total CVA?",
            "Show the total xVA breakdown",
            "Show potential future exposure",
        ],
    ),
    (
        "Stress & contagion",
        [
            "What happens in a property crash?",
            "What if NBFIs are downgraded?",
            "Which counterparty is most systemically important?",
            "Show the multi-round fire-sale cascade",
        ],
    ),
]


@dataclass(frozen=True)
class Exposure:
    head: str
    name: str
    connected: Decimal
    sector: str


def exposures(
    runner: QueryRunner, queries_dir: Path, visible: set[str] | None = None
) -> list[Exposure]:
    """Connected exposure per risk-owner group, scoped to the visible set."""
    owners = Q.connected_by_owner(runner, queries_dir)
    sectors = {
        _local(r["e"]): (r.get("sector") or "")
        for r in runner.select(_PREFIX + "SELECT ?e ?sector WHERE { ?e lens:sector ?sector }")
    }
    names = {
        _local(r["e"]): (r.get("name") or "")
        for r in runner.select(
            _PREFIX
            + "SELECT ?e ?name WHERE { ?e <http://www.w3.org/2000/01/rdf-schema#label> ?name }"
        )
    }
    out = [
        Exposure(head, names.get(head, head), exposure, sectors.get(head, ""))
        for head, exposure in owners.items()
        if visible is None or head in visible
    ]
    return sorted(out, key=lambda e: e.connected, reverse=True)


@dataclass(frozen=True)
class Dashboard:
    hhi: Q.DirectConnected
    cr10: Q.DirectConnected
    sectors: dict[str, Decimal]
    watchlist: list[Q.WatchlistRow]
    wwr: list[Q.WwrFlag]
    exposures: list[Exposure] = field(default_factory=list)
    countries: dict[str, Decimal] = field(default_factory=dict)
    ratings: dict[str, Decimal] = field(default_factory=dict)


def dashboard(
    runner: QueryRunner,
    queries_dir: Path,
    visible: set[str] | None = None,
    m2h: dict[str, str] | None = None,
) -> Dashboard:
    """Top-level dashboard: book-level metrics + scoped row-level views."""
    m2h = m2h or member_to_head(runner)
    watch = [
        w
        for w in Q.watchlist(runner, queries_dir)
        if visible is None or m2h.get(w.entity, w.entity) in visible
    ]
    wwr = [
        f
        for f in Q.wrong_way_risk(runner, queries_dir)
        if visible is None or m2h.get(f.borrower, f.borrower) in visible
    ]
    return Dashboard(
        hhi=Q.hhi(runner, queries_dir),
        cr10=Q.cr10(runner, queries_dir),
        sectors=Q.sector_shares(runner, queries_dir),
        watchlist=watch,
        wwr=wwr,
        exposures=exposures(runner, queries_dir, visible),
        countries=Q.country_shares(runner, queries_dir),
        ratings=Q.rating_shares(runner, queries_dir),
    )


@dataclass(frozen=True)
class GroupView:
    head: str
    direct_head_only: Decimal
    direct_group: Decimal
    connected: Decimal
    group_limit: Decimal
    limit_breached: bool
    contributions: list[dict[str, str]]


def group_view(runner: QueryRunner, queries_dir: Path, head: str) -> GroupView:
    """Single-counterparty drill-down: direct vs connected + contributing paths.

    Uses the group-aware M0 money-shot functions, so subsidiaries roll up
    correctly (not just loans booked to the head entity)."""
    head_iri = f"https://lens.example/id/{head}"
    h = C.headline(runner, queries_dir, head_iri)
    contributions = [
        {
            "type": c.contribution_type,
            "counterparty": c.counterparty_name or c.counterparty,
            "amount": str(c.amount),
        }
        for c in C.breakdown(runner, queries_dir, head_iri)
    ]
    return GroupView(
        head=head,
        direct_head_only=h.direct_head_only,
        direct_group=h.direct_group,
        connected=h.connected_total,
        group_limit=h.group_limit,
        limit_breached=h.limit_breached,
        contributions=contributions,
    )


def cascade_view(runner: QueryRunner, queries_dir: Path, nbfi: str) -> list[dict[str, str]]:
    """NBFI cascade chain (direct vs second-order) for the interconnectedness view."""
    nbfi_iri = f"https://lens.example/id/{nbfi}"
    return [
        {
            "type": c.contribution_type,
            "counterparty": c.counterparty_name or c.counterparty,
            "amount": str(c.amount),
        }
        for c in Q.nbfi_cascade(runner, queries_dir, nbfi_iri)
    ]
