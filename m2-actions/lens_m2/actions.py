"""Guarded actions: the ONLY sanctioned way to mutate the graph.

Every action follows the same path: build the proposed triples, validate the
candidate graph (current data + proposal) against SHACL, write via SPARQL Update
on success, compute derived flags (new limit breaches / wrong-way risk), and
audit the outcome — accepted or rejected — with who/what/when.

Soft-delete is a status change (loans -> ``closed``; others -> ``inactive``);
no triples are removed, so history is preserved while metrics exclude the
object. Referential-integrity is guarded on deactivate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rdflib import Graph

from . import graphbuild as G
from .audit import AuditLog, AuditRecord
from .derived import (
    Breach,
    CapitalSummary,
    CreditRisk,
    NetExposure,
    WwrFlag,
    capital_summary,
    expected_losses,
    limit_breaches,
    net_exposures,
    wrong_way_risk,
)
from .store import InMemoryStore, Store
from .validation import validate

if TYPE_CHECKING:
    from .importer import ImportReport

_PREFIX = "PREFIX lens: <https://lens.example/ontology/>\n"

# Identifiers are interpolated into SPARQL, so they are constrained to a strict
# safe charset (our ids look like LE-0001 / LN-1003 / GTY-2002 / LIM-LE-0001).
# Predicates come from a fixed allowlist. Together these close the injection
# surface: every interpolated piece is from a constrained domain.
_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_AMOUNT_PREDICATES = {"principalAmount", "limitAmount", "guaranteedAmount"}
_XSD_DECIMAL = "http://www.w3.org/2001/XMLSchema#decimal"


def _safe_iri(subject_id: str) -> str | None:
    """Return the full IRI for a strictly-valid bare id, else None."""
    if not _ID_RE.match(subject_id):
        return None
    return str(G.iri(subject_id))


@dataclass(frozen=True)
class ActionResult:
    accepted: bool
    action: str
    subject: str
    reason: str
    flags: list[str] = field(default_factory=list)


class ActionService:
    """Validate -> write -> flag -> audit, over a :class:`Store`."""

    def __init__(self, store: Store, audit: AuditLog, shapes_path: Path) -> None:
        self._store = store
        self._audit = audit
        self._shapes = shapes_path

    # --- internal helpers --------------------------------------------------- #

    def _breach_entities(self, breaches: list[Breach]) -> set[str]:
        return {b.entity for b in breaches}

    def _wwr_loans(self, flags: list[WwrFlag]) -> set[str]:
        return {f.loan for f in flags}

    def _guarded_create(
        self,
        proposed: Graph,
        subject: str,
        action: str,
        payload: dict[str, object],
        actor: str,
        role: str,
    ) -> ActionResult:
        snapshot = self._store.snapshot()
        before_breaches = self._breach_entities(limit_breaches(InMemoryStore(snapshot)))
        before_wwr = self._wwr_loans(wrong_way_risk(InMemoryStore(snapshot)))

        candidate = Graph()
        candidate += snapshot
        candidate += proposed
        result = validate(candidate, self._shapes)
        if not result.conforms:
            self._audit.record(
                AuditRecord(action, subject, actor, role, "rejected", result.reason, payload)
            )
            return ActionResult(False, action, subject, result.reason)

        self._store.update(G.insert_data(proposed))

        new_breaches = self._breach_entities(limit_breaches(self._store)) - before_breaches
        new_wwr = self._wwr_loans(wrong_way_risk(self._store)) - before_wwr
        flags = [f"limit-breach:{e}" for e in sorted(new_breaches)]
        flags += [f"wrong-way-risk:{ln}" for ln in sorted(new_wwr)]
        reason = "written" if not flags else "written; flagged " + ", ".join(flags)
        self._audit.record(
            AuditRecord(action, subject, actor, role, "accepted", reason, payload, flags)
        )
        return ActionResult(True, action, subject, reason, flags)

    # --- create ------------------------------------------------------------- #

    def create_entity(self, *, actor: str, role: str, **kw: object) -> ActionResult:
        g = G.entity_graph(**kw)  # type: ignore[arg-type]
        return self._guarded_create(g, str(kw["entity_id"]), "create-entity", kw, actor, role)

    def create_loan(self, *, actor: str, role: str, **kw: object) -> ActionResult:
        g = G.loan_graph(**kw)  # type: ignore[arg-type]
        return self._guarded_create(g, str(kw["loan_id"]), "create-loan", kw, actor, role)

    # CLAUDE.md's `record-exposure` action == booking a loan.
    record_exposure = create_loan

    def create_guaranty(self, *, actor: str, role: str, **kw: object) -> ActionResult:
        g = G.guaranty_graph(**kw)  # type: ignore[arg-type]
        return self._guarded_create(g, str(kw["guarantee_id"]), "create-guaranty", kw, actor, role)

    def create_collateral(self, *, actor: str, role: str, **kw: object) -> ActionResult:
        g = G.collateral_graph(**kw)  # type: ignore[arg-type]
        return self._guarded_create(
            g, str(kw["collateral_id"]), "create-collateral", kw, actor, role
        )

    def create_limit(self, *, actor: str, role: str, **kw: object) -> ActionResult:
        g = G.limit_graph(**kw)  # type: ignore[arg-type]
        return self._guarded_create(g, str(kw["limit_id"]), "create-limit", kw, actor, role)

    # --- update (re-validated; breaches recomputed) ------------------------- #

    def update_amount(
        self, *, subject_id: str, predicate: str, new_amount: int, actor: str, role: str
    ) -> ActionResult:
        """Update a single decimal amount (e.g. a loan principal or a limit)."""
        payload = {"predicate": predicate, "new_amount": new_amount}
        subject = _safe_iri(subject_id)
        if (
            subject is None
            or predicate not in _AMOUNT_PREDICATES
            or not isinstance(new_amount, int)
        ):
            reason = "invalid subject id, predicate, or amount"
            self._audit.record(
                AuditRecord("update-amount", subject_id, actor, role, "rejected", reason, payload)
            )
            return ActionResult(False, "update-amount", subject_id, reason)

        # subject is a validated IRI, predicate is allowlisted, amount is an int.
        update = (
            f"{_PREFIX}DELETE {{ <{subject}> lens:{predicate} ?old }} "
            f'INSERT {{ <{subject}> lens:{predicate} "{new_amount}"^^<{_XSD_DECIMAL}> }} '
            f"WHERE {{ <{subject}> lens:{predicate} ?old }}"
        )
        # Validate BEFORE touching the live store: apply to a snapshot copy first.
        candidate = self._store.snapshot()
        candidate.update(update)
        result = validate(candidate, self._shapes)
        if not result.conforms:
            self._audit.record(
                AuditRecord(
                    "update-amount", subject_id, actor, role, "rejected", result.reason, payload
                )
            )
            return ActionResult(False, "update-amount", subject_id, result.reason)

        before = self._breach_entities(limit_breaches(self._store))
        self._store.update(update)
        new_breaches = self._breach_entities(limit_breaches(self._store)) - before
        flags = [f"limit-breach:{e}" for e in sorted(new_breaches)]
        reason = "updated" if not flags else "updated; flagged " + ", ".join(flags)
        self._audit.record(
            AuditRecord(
                "update-amount", subject_id, actor, role, "accepted", reason, payload, flags
            )
        )
        return ActionResult(True, "update-amount", subject_id, reason, flags)

    # --- deactivate (soft-delete) ------------------------------------------- #

    def deactivate(self, *, subject_id: str, kind: str, actor: str, role: str) -> ActionResult:
        subject = _safe_iri(subject_id)
        if subject is None:
            reason = "invalid subject id"
            self._audit.record(
                AuditRecord(
                    "deactivate", subject_id, actor, role, "rejected", reason, {"kind": kind}
                )
            )
            return ActionResult(False, "deactivate", subject_id, reason)
        guard = self._referential_guard(subject, kind)
        if guard:
            self._audit.record(
                AuditRecord(
                    "deactivate", subject_id, actor, role, "rejected", guard, {"kind": kind}
                )
            )
            return ActionResult(False, "deactivate", subject_id, guard)

        new_status = "closed" if kind == "loan" else "inactive"
        update = (
            f"{_PREFIX}DELETE {{ <{subject}> lens:status ?s }} "
            f'INSERT {{ <{subject}> lens:status "{new_status}" }} '
            f"WHERE {{ <{subject}> lens:status ?s }}"
        )
        self._store.update(update)
        reason = f"status set to {new_status} (excluded from metrics; history preserved)"
        self._audit.record(
            AuditRecord("deactivate", subject_id, actor, role, "accepted", reason, {"kind": kind})
        )
        return ActionResult(True, "deactivate", subject_id, reason)

    def _referential_guard(self, subject: str, kind: str) -> str | None:
        """Block deactivating an entity that still backs active exposure.

        ``subject`` is a pre-validated IRI (see :func:`_safe_iri`), so it is safe
        to interpolate into the SELECT.
        """
        if kind != "entity":
            return None
        q = (
            f"{_PREFIX}SELECT ?ref WHERE {{ "
            f'{{ ?ref lens:borrower <{subject}> ; lens:status "active" . }} '
            f'UNION {{ ?ref lens:lender <{subject}> ; lens:status "active" . }} '
            f'UNION {{ ?ref lens:guarantor <{subject}> ; lens:status "active" . }} }} LIMIT 1'
        )
        if self._store.select(q):
            return "entity still referenced by an active loan or guaranty; deactivate those first"
        return None

    # --- bring-your-own-data import (guarded, audited) ---------------------- #

    def import_dataset(
        self,
        rows_by_table: dict[str, list[dict[str, str]]],
        *,
        dataset_name: str,
        actor: str,
        role: str,
        allow_partial: bool = False,
    ) -> ImportReport:
        """Validate + load a user TEST dataset through this guarded layer."""
        from .importer import import_dataset as _import_dataset

        return _import_dataset(
            rows_by_table,
            store=self._store,
            audit=self._audit,
            shapes_path=self._shapes,
            dataset_name=dataset_name,
            actor=actor,
            role=role,
            allow_partial=allow_partial,
        )

    # --- explicit flag actions --------------------------------------------- #

    def net_exposures(self) -> list[NetExposure]:
        """Read-only: counterparties whose exposure is reduced by collateral/netting."""
        return net_exposures(self._store)

    def expected_losses(self) -> list[CreditRisk]:
        """Read-only: per-counterparty EAD/PD/EL/RWA/capital (simplified, point-in-time)."""
        return expected_losses(self._store)

    def capital_summary(self) -> CapitalSummary:
        """Read-only: book-level EAD/EL/RWA/capital."""
        return capital_summary(self._store)

    def flag_limit_breaches(self, *, actor: str, role: str) -> list[Breach]:
        breaches = limit_breaches(self._store)
        for b in breaches:
            self._audit.record(
                AuditRecord(
                    "flag-limit-breach",
                    b.entity,
                    actor,
                    role,
                    "accepted",
                    f"connected {b.connected} >= limit {b.limit}",
                    {"connected": str(b.connected), "limit": str(b.limit)},
                    ["limit-breach"],
                )
            )
        return breaches

    def flag_wrong_way_risk(self, *, actor: str, role: str) -> list[WwrFlag]:
        flags = wrong_way_risk(self._store)
        for f in flags:
            self._audit.record(
                AuditRecord(
                    "flag-wrong-way-risk",
                    f.loan,
                    actor,
                    role,
                    "accepted",
                    f"collateral {f.collateral} issued by same group {f.group} as borrower",
                    {"issuer": f.issuer, "group": f.group},
                    ["wrong-way-risk"],
                )
            )
        return flags
