"""Typed records for the synthetic source tables.

These mirror the CSV columns the generator emits (entities, loans, guarantees,
collateral, limits) — "source-style tables as if from separate systems" — and
are the in-memory form the metrics oracle and the RDF loader both consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Allowed counterparty types (enum carried as a string tag on the entity).
COUNTERPARTY_TYPES = frozenset({"bank", "corporate", "nbfi", "government"})

CURRENCY = "SGD"


@dataclass(frozen=True)
class Entity:
    """A legal entity (counterparty or the lending institution)."""

    entity_id: str
    name: str
    counterparty_type: str
    sector: str
    parent_id: str | None = None  # immediate owner, for ownership/UBO chains
    eligible_capital: int | None = None  # set on the lending institution
    annual_revenue: int | None = None  # set on corporate counterparties
    country: str | None = None  # ISO-style country code, for country concentration
    rating: str | None = None  # credit rating grade (AAA..CCC), for rating concentration

    def __post_init__(self) -> None:
        if self.counterparty_type not in COUNTERPARTY_TYPES:
            raise ValueError(f"{self.entity_id}: bad counterparty_type {self.counterparty_type!r}")


@dataclass(frozen=True)
class Loan:
    """A loan the institution (lender) has booked to a borrower.

    ``status`` is ``active`` or ``closed``; only active loans count toward
    exposure (closed/soft-deleted loans are preserved for audit but excluded
    from metrics — see M2).
    """

    loan_id: str
    lender_id: str
    borrower_id: str
    principal: int
    currency: str = CURRENCY
    status: str = "active"
    # Remaining tenor in years, for forward-looking exposure (PFE/EE) and CVA.
    # Optional (default 3y) so pre-existing / BYOD data without it still loads.
    maturity_years: int = 3


@dataclass(frozen=True)
class Guarantee:
    """A guarantee given by a guarantor over a specific loan."""

    guarantee_id: str
    guarantor_id: str
    guaranteed_loan_id: str
    amount: int
    currency: str = CURRENCY


@dataclass(frozen=True)
class Collateral:
    """Collateral pledged against one or more loans (shared if more than one).

    ``issuer_id`` is set only when the collateral is a security; a same-group
    issuer vs borrower is the structural wrong-way-risk case.
    """

    collateral_id: str
    description: str
    pledged_by_id: str
    secures_loan_ids: tuple[str, ...]
    issuer_id: str | None = None
    # Credit-risk mitigation: market value of the collateral and the supervisory
    # haircut (percent, 0-100). Eligible mitigant = value * (1 - haircut/100).
    # Optional, so pre-existing collateral (no CRM data) still loads.
    collateral_value: int | None = None
    haircut_pct: int = 0


@dataclass(frozen=True)
class Limit:
    """A single-name / group credit limit on connected exposure."""

    limit_id: str
    entity_id: str
    limit_amount: int
    currency: str = CURRENCY


@dataclass(frozen=True)
class DatasetSpec:
    """A complete labelled dataset variant (``calm`` or ``stressed``)."""

    name: str
    entities: list[Entity]
    loans: list[Loan]
    guarantees: list[Guarantee]
    collateral: list[Collateral]
    limits: list[Limit]
    description: str = ""
    # Per-table provenance note, surfaced in lineage output.
    sources: dict[str, str] = field(default_factory=dict)

    def entity(self, entity_id: str) -> Entity:
        for e in self.entities:
            if e.entity_id == entity_id:
                return e
        raise KeyError(entity_id)

    def loan(self, loan_id: str) -> Loan:
        for ln in self.loans:
            if ln.loan_id == loan_id:
                return ln
        raise KeyError(loan_id)
