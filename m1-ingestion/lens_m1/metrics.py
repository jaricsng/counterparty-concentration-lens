"""Reference (oracle) computation of connected exposure and concentration metrics.

Plain-Python ground truth used to (a) verify the engineered datasets land in the
intended risk bands and (b) serve as the expected-value oracle that M0's SPARQL
metric queries are tested against in the next step. Implements
docs/concentration-metrics.md §3 / §9.

Two complementary exposure notions (both faithful to the spec, each used where it
is the right question):

* **Single-name connected exposure** (overlap, the M0 model): direct loans to
  group members + guarantees GIVEN by members over outside loans + outside loans
  SHARING collateral with a member loan. A guarantee counts for both the
  guarantor and the borrower — that overlap is the point (each name's true
  reach). Used for single-name utilisation, the watchlist, UBO aggregation and
  the NBFI cascade. (§3.1, §3.5, §9)

* **Risk-owner attribution** (each loan counted ONCE): a loan's exposure is
  attributed to the guarantor's group where the loan is guaranteed by another
  group, otherwise to the borrower's ultimate parent. This avoids double-counting
  and reflects where risk truly lands — the Archegos lesson — and is the basis
  for the portfolio metrics HHI / CR10 / sector. (§3.2 – §3.4)

Only ``active`` loans count toward exposure.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .spec import DatasetSpec, Loan

# Utilisation band thresholds (fractions of the limit). §9.2.
AMBER_FROM = Decimal("0.75")
RED_FROM = Decimal("1.00")


def _active_loans(spec: DatasetSpec) -> list[Loan]:
    return [ln for ln in spec.loans if ln.status == "active"]


def _ubo(spec: DatasetSpec, entity_id: str) -> str:
    """Walk the ownership chain to the ultimate parent (loop-guarded)."""
    seen: set[str] = set()
    current = entity_id
    while True:
        if current in seen:  # circular ownership guard
            return current
        seen.add(current)
        parent = spec.entity(current).parent_id
        if parent is None:
            return current
        current = parent


def ultimate_parent(spec: DatasetSpec, entity_id: str) -> str:
    """Public alias for the loop-guarded UBO walk."""
    return _ubo(spec, entity_id)


def top_level_names(spec: DatasetSpec) -> list[str]:
    """Entities that head a counterparty (no parent), excluding the lender — the
    granularity at which connected concentration is measured."""
    names = [e.entity_id for e in spec.entities if e.parent_id is None]
    lenders = {ln.lender_id for ln in spec.loans}
    return [n for n in names if n not in lenders]


def group_members(spec: DatasetSpec, head: str) -> set[str]:
    """``head`` plus every entity whose ownership chain rolls up to it."""
    return {e.entity_id for e in spec.entities if _ubo(spec, e.entity_id) == head} | {head}


def _borrower_of(spec: DatasetSpec, loan_id: str) -> str:
    return spec.loan(loan_id).borrower_id


def direct_exposure(spec: DatasetSpec, entity_id: str) -> Decimal:
    """Active loans booked directly to this exact entity (no roll-up)."""
    return Decimal(sum(ln.principal for ln in _active_loans(spec) if ln.borrower_id == entity_id))


# --------------------------------------------------------------------------- #
#  Credit-risk mitigation: netting + collateral (post-CRM net exposure)
# --------------------------------------------------------------------------- #


def collateral_mitigant(spec: DatasetSpec, entity_id: str) -> Decimal:
    """Eligible (post-haircut) collateral dedicated to one counterparty's loans.

    Netting here is one set per counterparty: a collateral counts only if EVERY
    active loan it secures is a loan to this counterparty. Collateral shared across
    different counterparties is conservatively excluded (no allocation guesswork,
    no double counting). Eligible value = value * (1 - haircut).
    """
    cp_loans = {ln.loan_id for ln in _active_loans(spec) if ln.borrower_id == entity_id}
    total = Decimal(0)
    for c in spec.collateral:
        if c.collateral_value is None:
            continue
        secured = set(c.secures_loan_ids)
        if secured and secured <= cp_loans:
            total += Decimal(c.collateral_value) * (Decimal(100 - c.haircut_pct) / 100)
    return total


def net_exposure(spec: DatasetSpec, entity_id: str) -> Decimal:
    """Single-name exposure after credit-risk mitigation: max(0, gross - mitigant)."""
    gross = direct_exposure(spec, entity_id)
    return max(Decimal(0), gross - collateral_mitigant(spec, entity_id))


# --------------------------------------------------------------------------- #
#  Single-name connected exposure (overlap model)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ConnectedExposure:
    """Connected exposure to a name, broken out by contribution type."""

    head: str
    direct: Decimal
    guarantees_given: Decimal
    shared_collateral: Decimal

    @property
    def total(self) -> Decimal:
        return self.direct + self.guarantees_given + self.shared_collateral


def connected_exposure(spec: DatasetSpec, head: str) -> ConnectedExposure:
    """Connected exposure for the group headed by ``head`` (M0 definition)."""
    members = group_members(spec, head)
    active = _active_loans(spec)
    active_ids = {ln.loan_id for ln in active}

    direct = Decimal(sum(ln.principal for ln in active if ln.borrower_id in members))

    guarantees = Decimal(
        sum(
            g.amount
            for g in spec.guarantees
            if g.guarantor_id in members
            and g.guaranteed_loan_id in active_ids
            and _borrower_of(spec, g.guaranteed_loan_id) not in members
        )
    )

    # Outside loans sharing collateral with a member loan (each counted once).
    outside_loans: set[str] = set()
    for col in spec.collateral:
        secured = [lid for lid in col.secures_loan_ids if lid in active_ids]
        if not any(_borrower_of(spec, lid) in members for lid in secured):
            continue
        for lid in secured:
            if _borrower_of(spec, lid) not in members:
                outside_loans.add(lid)
    shared = Decimal(sum(spec.loan(lid).principal for lid in outside_loans))

    return ConnectedExposure(head, direct, guarantees, shared)


def connected_vector(spec: DatasetSpec) -> dict[str, Decimal]:
    """Single-name connected exposure per top-level name (overlap model)."""
    return {n: connected_exposure(spec, n).total for n in top_level_names(spec)}


# --------------------------------------------------------------------------- #
#  Risk-owner attribution (each loan counted once) — basis for HHI/CR10/sector
# --------------------------------------------------------------------------- #


def risk_owner(spec: DatasetSpec, loan: Loan) -> str:
    """The group that ultimately carries a loan's risk.

    If the loan is guaranteed by an entity in a *different* group, risk lands on
    that guarantor's ultimate parent; otherwise on the borrower's ultimate
    parent.
    """
    borrower_ubo = _ubo(spec, loan.borrower_id)
    for g in spec.guarantees:
        if g.guaranteed_loan_id != loan.loan_id:
            continue
        guarantor_ubo = _ubo(spec, g.guarantor_id)
        if guarantor_ubo != borrower_ubo:
            return guarantor_ubo
    return borrower_ubo


def attributed_vector(spec: DatasetSpec) -> dict[str, Decimal]:
    """Exposure per risk-owner group (each active loan attributed once)."""
    out: dict[str, Decimal] = {}
    for ln in _active_loans(spec):
        owner = risk_owner(spec, ln)
        out[owner] = out.get(owner, Decimal(0)) + Decimal(ln.principal)
    return out


def direct_vector(spec: DatasetSpec) -> dict[str, Decimal]:
    """Direct exposure per immediate borrower (excludes the lender)."""
    lenders = {ln.lender_id for ln in spec.loans}
    borrowers = {ln.borrower_id for ln in _active_loans(spec) if ln.borrower_id not in lenders}
    return {b: direct_exposure(spec, b) for b in borrowers}


def hhi(vector: dict[str, Decimal]) -> Decimal:
    """Herfindahl–Hirschman Index, fractional form (0..1). §3.3."""
    total = sum(vector.values(), Decimal(0))
    if total == 0:
        return Decimal(0)
    return sum(((v / total) ** 2 for v in vector.values()), Decimal(0))


def cr10(vector: dict[str, Decimal]) -> Decimal:
    """Top-10 concentration ratio. §3.2."""
    total = sum(vector.values(), Decimal(0))
    if total == 0:
        return Decimal(0)
    top = sorted(vector.values(), reverse=True)[:10]
    return sum(top, Decimal(0)) / total


def sector_shares(spec: DatasetSpec) -> dict[str, Decimal]:
    """Share of attributed exposure by the risk-owner's sector. §3.4.

    Exposure guaranteed by an NBFI therefore counts toward financial-services
    concentration — surfacing hidden non-bank-financial sector risk.
    """
    vector = attributed_vector(spec)
    total = sum(vector.values(), Decimal(0))
    if total == 0:
        return {}
    shares: dict[str, Decimal] = {}
    for name, exposure in vector.items():
        sector = spec.entity(name).sector
        shares[sector] = shares.get(sector, Decimal(0)) + exposure
    return {s: v / total for s, v in shares.items()}


def _attribute_shares(spec: DatasetSpec, attr: str, default: str) -> dict[str, Decimal]:
    """Share of attributed (risk-owner) exposure grouped by an entity attribute."""
    vector = attributed_vector(spec)
    total = sum(vector.values(), Decimal(0))
    if total == 0:
        return {}
    shares: dict[str, Decimal] = {}
    for name, exposure in vector.items():
        key = getattr(spec.entity(name), attr) or default
        shares[key] = shares.get(key, Decimal(0)) + exposure
    return {k: v / total for k, v in shares.items()}


def country_shares(spec: DatasetSpec) -> dict[str, Decimal]:
    """Share of attributed exposure by the risk-owner's country of risk."""
    return _attribute_shares(spec, "country", "unknown")


def rating_shares(spec: DatasetSpec) -> dict[str, Decimal]:
    """Share of attributed exposure by the risk-owner's credit-rating grade."""
    return _attribute_shares(spec, "rating", "unrated")


# --------------------------------------------------------------------------- #
#  Single-name utilisation / watchlist bands (§9.2)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Utilisation:
    name: str
    connected: Decimal
    limit: Decimal
    band: str  # green | amber | red

    @property
    def ratio(self) -> Decimal:
        return self.connected / self.limit if self.limit else Decimal(0)


def _limit_for(spec: DatasetSpec, entity_id: str) -> Decimal | None:
    for lim in spec.limits:
        if lim.entity_id == entity_id:
            return Decimal(lim.limit_amount)
    return None


def band_for(ratio: Decimal) -> str:
    if ratio >= RED_FROM:
        return "red"
    if ratio >= AMBER_FROM:
        return "amber"
    return "green"


def utilisations(spec: DatasetSpec) -> list[Utilisation]:
    """Utilisation + band for every entity that has a limit (connected basis).

    Includes subsidiaries with their own limits, so a subsidiary approaching its
    individual limit shows on the watchlist alongside group heads.
    """
    out: list[Utilisation] = []
    for lim in spec.limits:
        limit = Decimal(lim.limit_amount)
        connected = connected_exposure(spec, lim.entity_id).total
        out.append(Utilisation(lim.entity_id, connected, limit, band_for(connected / limit)))
    return sorted(out, key=lambda u: u.ratio, reverse=True)


# --------------------------------------------------------------------------- #
#  UBO aggregation (§9.1) and structural wrong-way risk (§3.6)
# --------------------------------------------------------------------------- #


def subsidiary_breach_check(spec: DatasetSpec, head: str) -> dict[str, object]:
    """UBO-aggregated connected exposure vs limit, plus whether any individual
    subsidiary breaches its own limit. The UBO story is a breach at the top with
    every subsidiary individually within limit."""
    members = sorted(group_members(spec, head) - {head})
    ubo_connected = connected_exposure(spec, head).total
    ubo_limit = _limit_for(spec, head)
    sub_breaches = []
    for sub in members:
        sub_limit = _limit_for(spec, sub)
        if sub_limit is not None and connected_exposure(spec, sub).total >= sub_limit:
            sub_breaches.append(sub)
    return {
        "head": head,
        "ubo_connected": ubo_connected,
        "ubo_limit": ubo_limit,
        "ubo_breaches": bool(ubo_limit is not None and ubo_connected > ubo_limit),
        "subsidiaries": members,
        "subsidiary_breaches": sub_breaches,
    }


def wrong_way_risk_flags(spec: DatasetSpec) -> list[dict[str, str]]:
    """Loans whose collateral issuer is in the same group as the borrower. §3.6."""
    flags: list[dict[str, str]] = []
    active_ids = {ln.loan_id for ln in _active_loans(spec)}
    for col in spec.collateral:
        if col.issuer_id is None:
            continue
        issuer_ubo = _ubo(spec, col.issuer_id)
        for lid in col.secures_loan_ids:
            if lid not in active_ids:
                continue
            borrower = _borrower_of(spec, lid)
            if _ubo(spec, borrower) == issuer_ubo:
                flags.append(
                    {
                        "loan": lid,
                        "borrower": borrower,
                        "collateral": col.collateral_id,
                        "issuer": col.issuer_id,
                        "group": issuer_ubo,
                    }
                )
    return flags
