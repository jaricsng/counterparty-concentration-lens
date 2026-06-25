"""Derived (computed) checks that run on the live store after a write.

The connected single-name limit breach is a multi-hop AGGREGATION, not a
per-node SHACL rule. Rather than push a heavy nested query into the store on
every action, we pull the relevant facts with a handful of cheap SELECTs and
compute connected exposure in Python (the same definition as the M0/M1 model).

Everything is status-aware: only ``active`` loans / guaranties / collateral
count, so a soft-deleted object drops out of the metrics immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from lens_m1.credit_risk import CAPITAL_RATIO, expected_loss, pd_for, rw_for

from .store import Store

_PREFIX = "PREFIX lens: <https://lens.example/ontology/>\n"


def _local(iri: str | None) -> str:
    return iri.rsplit("/", 1)[-1] if iri else ""


@dataclass
class _Facts:
    parent: dict[str, str]
    limits: dict[str, Decimal]
    loans: dict[str, tuple[str, Decimal]]  # loan -> (borrower, principal)
    guarantees: list[tuple[str, str, Decimal]]  # (guarantor, guaranteed_loan, amount)
    collateral: dict[str, list[str]]  # collateral -> [loan, ...]
    crm: dict[str, tuple[Decimal, Decimal]]  # collateral -> (value, haircut fraction)


def _facts(store: Store) -> _Facts:
    parent = {
        _local(r["c"]): _local(r["p"])
        for r in store.select(_PREFIX + "SELECT ?c ?p WHERE { ?c lens:isSubsidiaryOf ?p }")
    }
    limits = {
        _local(r["e"]): Decimal(r["limit"] or 0)
        for r in store.select(
            _PREFIX + "SELECT ?e ?limit WHERE { ?e lens:hasLimit ?l . "
            '?l lens:limitAmount ?limit ; lens:status "active" . }'
        )
    }
    loans = {
        _local(r["loan"]): (_local(r["b"]), Decimal(r["amt"] or 0))
        for r in store.select(
            _PREFIX + "SELECT ?loan ?b ?amt WHERE { ?loan lens:borrower ?b ; "
            'lens:principalAmount ?amt ; lens:status "active" . }'
        )
    }
    guarantees = [
        (_local(r["gtor"]), _local(r["gl"]), Decimal(r["amt"] or 0))
        for r in store.select(
            _PREFIX + "SELECT ?gtor ?gl ?amt WHERE { ?g lens:guarantor ?gtor ; "
            'lens:guaranteedLoan ?gl ; lens:guaranteedAmount ?amt ; lens:status "active" . }'
        )
    ]
    collateral: dict[str, list[str]] = {}
    for r in store.select(
        _PREFIX + 'SELECT ?col ?loan WHERE { ?col lens:securesLoan ?loan ; lens:status "active" . }'
    ):
        collateral.setdefault(_local(r["col"]), []).append(_local(r["loan"]))
    crm = {
        _local(r["col"]): (Decimal(r["val"] or 0), Decimal(r["hc"] or 0))
        for r in store.select(
            _PREFIX + "SELECT ?col ?val ?hc WHERE { ?col lens:collateralValue ?val ; "
            'lens:haircut ?hc ; lens:status "active" . }'
        )
    }
    return _Facts(parent, limits, loans, guarantees, collateral, crm)


def _ancestors(facts: _Facts, entity: str) -> set[str]:
    seen: set[str] = set()
    current = entity
    while current in facts.parent and facts.parent[current] not in seen:
        current = facts.parent[current]
        seen.add(current)
    return seen


def _members(facts: _Facts, head: str) -> set[str]:
    everyone = (
        set(facts.parent)
        | set(facts.parent.values())
        | {b for b, _ in facts.loans.values()}
        | set(facts.limits)
    )
    return {e for e in everyone if head in _ancestors(facts, e)} | {head}


def _connected(facts: _Facts, head: str) -> Decimal:
    members = _members(facts, head)
    direct = sum((amt for b, amt in facts.loans.values() if b in members), Decimal(0))
    guar = sum(
        (
            amt
            for gtor, gl, amt in facts.guarantees
            if gtor in members and gl in facts.loans and facts.loans[gl][0] not in members
        ),
        Decimal(0),
    )
    outside: set[str] = set()
    for loan_ids in facts.collateral.values():
        active = [lid for lid in loan_ids if lid in facts.loans]
        if any(facts.loans[lid][0] in members for lid in active):
            outside.update(lid for lid in active if facts.loans[lid][0] not in members)
    shared = sum((facts.loans[lid][1] for lid in outside), Decimal(0))
    return direct + guar + shared


@dataclass(frozen=True)
class Breach:
    entity: str
    connected: Decimal
    limit: Decimal

    @property
    def utilisation(self) -> Decimal:
        return self.connected / self.limit if self.limit else Decimal(0)


def connected_exposure(store: Store, entity_iri: str) -> Decimal:
    """Status-aware connected exposure for one entity."""
    return _connected(_facts(store), _local(entity_iri))


def _collateral_mitigant(facts: _Facts, cp: str) -> Decimal:
    """Eligible (post-haircut) collateral dedicated to one counterparty's loans."""
    cp_loans = {loan for loan, (b, _amt) in facts.loans.items() if b == cp}
    total = Decimal(0)
    for col, loans in facts.collateral.items():
        if col not in facts.crm:
            continue
        secured = set(loans)
        if secured and secured <= cp_loans:
            value, haircut = facts.crm[col]
            total += value * (1 - haircut)
    return total


def net_exposure(store: Store, entity_iri: str) -> Decimal:
    """Single-name exposure after credit-risk mitigation: max(0, gross - mitigant)."""
    facts = _facts(store)
    cp = _local(entity_iri)
    gross = sum((amt for b, amt in facts.loans.values() if b == cp), Decimal(0))
    return max(Decimal(0), gross - _collateral_mitigant(facts, cp))


@dataclass(frozen=True)
class NetExposure:
    entity: str
    name: str
    sector: str
    gross: Decimal
    mitigant: Decimal
    net: Decimal


def net_exposures(store: Store) -> list[NetExposure]:
    """Counterparties with eligible collateral: gross -> net (post-CRM) exposure."""
    facts = _facts(store)
    names = {
        _local(r["e"]): (r["n"] or "")
        for r in store.select(
            "SELECT ?e ?n WHERE { ?e <http://www.w3.org/2000/01/rdf-schema#label> ?n }"
        )
    }
    sectors = {
        _local(r["e"]): (r["s"] or "")
        for r in store.select(_PREFIX + "SELECT ?e ?s WHERE { ?e lens:sector ?s }")
    }
    rows: list[NetExposure] = []
    for cp in sorted({b for b, _ in facts.loans.values()}):
        mitigant = _collateral_mitigant(facts, cp)
        if mitigant <= 0:
            continue
        gross = sum((amt for b, amt in facts.loans.values() if b == cp), Decimal(0))
        rows.append(
            NetExposure(
                cp,
                names.get(cp, cp),
                sectors.get(cp, ""),
                gross,
                mitigant,
                max(Decimal(0), gross - mitigant),
            )
        )
    return rows


@dataclass(frozen=True)
class CreditRisk:
    entity: str
    name: str
    sector: str
    rating: str
    ead: Decimal
    pd: Decimal
    el: Decimal
    rwa: Decimal
    capital: Decimal


def _entity_meta(store: Store) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    names = {
        _local(r["e"]): (r["n"] or "")
        for r in store.select(
            "SELECT ?e ?n WHERE { ?e <http://www.w3.org/2000/01/rdf-schema#label> ?n }"
        )
    }
    meta = {
        _local(r["e"]): (r["s"] or "", r["rt"] or "")
        for r in store.select(
            _PREFIX + "SELECT ?e ?s ?rt WHERE { ?e lens:sector ?s . "
            "OPTIONAL { ?e lens:rating ?rt } }"
        )
    }
    return names, meta


def expected_losses(store: Store) -> list[CreditRisk]:
    """Per-counterparty EAD/PD/EL/RWA/capital from the live store (status-aware).

    EAD = net (post-collateral) exposure; PD/RW from rating; EL = PD x LGD x EAD.
    Simplified point-in-time view — see lens_m1.credit_risk for the honesty caveats.
    """
    facts = _facts(store)
    names, meta = _entity_meta(store)
    rows: list[CreditRisk] = []
    for cp in sorted({b for b, _ in facts.loans.values()}):
        gross = sum((amt for b, amt in facts.loans.values() if b == cp), Decimal(0))
        ead = max(Decimal(0), gross - _collateral_mitigant(facts, cp))
        sector, rating = meta.get(cp, ("", ""))
        rwa = rw_for(rating) * ead
        rows.append(
            CreditRisk(
                cp,
                names.get(cp, cp),
                sector,
                rating or "unrated",
                ead,
                pd_for(rating),
                expected_loss(ead, rating),
                rwa,
                CAPITAL_RATIO * rwa,
            )
        )
    return sorted(rows, key=lambda r: r.el, reverse=True)


@dataclass(frozen=True)
class CapitalSummary:
    total_ead: Decimal
    total_el: Decimal
    total_rwa: Decimal
    total_capital: Decimal


def capital_summary(store: Store) -> CapitalSummary:
    """Book-level EAD / EL / RWA / capital from the live store."""
    rows = expected_losses(store)
    total_rwa = sum((r.rwa for r in rows), Decimal(0))
    return CapitalSummary(
        total_ead=sum((r.ead for r in rows), Decimal(0)),
        total_el=sum((r.el for r in rows), Decimal(0)),
        total_rwa=total_rwa,
        total_capital=CAPITAL_RATIO * total_rwa,
    )


def limit_breaches(store: Store) -> list[Breach]:
    """Names whose connected exposure meets or exceeds their limit."""
    facts = _facts(store)
    breaches = [
        Breach(e, _connected(facts, e), lim)
        for e, lim in facts.limits.items()
        if lim and _connected(facts, e) >= lim
    ]
    return sorted(breaches, key=lambda b: b.utilisation, reverse=True)


@dataclass(frozen=True)
class WwrFlag:
    loan: str
    borrower: str
    collateral: str
    issuer: str
    group: str


_WWR = (
    _PREFIX + "SELECT ?loan ?borrower ?collateral ?issuer WHERE { "
    '?collateral lens:collateralIssuer ?issuer ; lens:securesLoan ?loan ; lens:status "active" . '
    '?loan lens:borrower ?borrower ; lens:status "active" . }'
)


def wrong_way_risk(store: Store) -> list[WwrFlag]:
    """Active loans whose active collateral is issued by the borrower's group."""
    facts = _facts(store)

    def ubo(e: str) -> str:
        anc = _ancestors(facts, e)
        # the ancestor with no parent (or e itself)
        for a in anc:
            if a not in facts.parent:
                return a
        return e

    flags: list[WwrFlag] = []
    for r in store.select(_WWR):
        borrower = _local(r["borrower"])
        issuer = _local(r["issuer"])
        if ubo(borrower) == ubo(issuer):
            flags.append(
                WwrFlag(_local(r["loan"]), borrower, _local(r["collateral"]), issuer, ubo(borrower))
            )
    return flags
