"""Deterministic systemic-contagion cascade — default propagation over the graph.

DELIBERATELY DETERMINISTIC and clearly labelled — **not** a calibrated systemic-risk
model and **not** a Monte-Carlo network simulation. We propagate a single seed default
through the EXPOSURE GRAPH the Lens already builds, in two hops:

  * the seed's whole ownership group defaults together (control contagion);
  * **direct loss**  = LGD·EAD on the group's loans, *less* recovery from any SOLVENT
    (non-defaulted) guarantor;
  * **contagion loss** = LGD·EAD on OUTSIDE loans that lose their guarantor because the
    seed group *was* the guarantor — protection that evaporates when the group fails.

Total = direct + contagion; the amplification ratio (total ÷ direct) shows the
multi-hop effect. This turns the Lens's connected-exposure graph into a loss-propagation
view: which counterparty's failure hurts most, *including* second-order contagion.

See docs/ccr-coverage.md for what stays out of scope (calibrated network contagion,
macro/correlated shocks, fire-sale / liquidity spirals).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from . import credit_risk
from .metrics import _active_loans, _borrower_of, group_members, net_exposure, top_level_names
from .spec import DatasetSpec

LGD = credit_risk.LGD


def _solvent_guarantor(spec: DatasetSpec, loan_id: str, defaulted: set[str]) -> bool:
    """True if ``loan_id`` is guaranteed by an entity OUTSIDE the defaulted set."""
    return any(
        g.guaranteed_loan_id == loan_id and g.guarantor_id not in defaulted for g in spec.guarantees
    )


@dataclass(frozen=True)
class Cascade:
    seed: str  # group head whose default seeds the cascade
    group_size: int
    direct_loss: Decimal  # LGD·EAD on the group's own unprotected loans
    contagion_loss: Decimal  # LGD·EAD on outside loans that lost their guarantor
    total_loss: Decimal

    @property
    def amplification(self) -> Decimal:
        """Total loss ÷ direct loss — how much contagion multiplies the first-order hit."""
        return self.total_loss / self.direct_loss if self.direct_loss else Decimal(0)


def cascade(spec: DatasetSpec, head: str) -> Cascade:
    """Loss cascade if the group headed by ``head`` defaults (control + guarantee contagion)."""
    defaulted = group_members(spec, head)
    active = _active_loans(spec)
    by_id = {ln.loan_id: ln for ln in active}

    direct = Decimal(0)
    for ln in active:
        if ln.borrower_id in defaulted and not _solvent_guarantor(spec, ln.loan_id, defaulted):
            direct += Decimal(LGD) * ln.principal

    # outside loans that lose their guarantor (the seed group was the guarantor)
    unprotected: set[str] = set()
    for g in spec.guarantees:
        if g.guarantor_id in defaulted:
            gln = by_id.get(g.guaranteed_loan_id)
            if gln is not None and _borrower_of(spec, gln.loan_id) not in defaulted:
                unprotected.add(gln.loan_id)
    contagion = sum((Decimal(LGD) * by_id[lid].principal for lid in unprotected), Decimal(0))

    return Cascade(
        seed=head,
        group_size=len(defaulted),
        direct_loss=direct,
        contagion_loss=contagion,
        total_loss=direct + contagion,
    )


def systemic_ranking(spec: DatasetSpec) -> list[Cascade]:
    """Cascade for every counterparty group, sorted by total loss desc (most systemic first)."""
    rows = [cascade(spec, head) for head in top_level_names(spec)]
    return sorted(rows, key=lambda c: c.total_loss, reverse=True)


# --------------------------------------------------------------------------- #
#  Multi-round cascade with fire-sale spirals — an ITERATIVE fixed point.
#  Each round: defaulters' guarantee obligations land on solvent guarantors; a
#  guarantor whose obligations exceed its (fire-sale-shrunk) buffer defaults too;
#  liquidating defaulters' collateral lifts a market haircut that deepens losses.
#  Deterministic fixed-point iteration — NOT a calibrated network/Monte-Carlo model.
# --------------------------------------------------------------------------- #

BUFFER_FRACTION = 0.3  # loss-absorbing buffer as a fraction of an entity's net exposure
FIRESALE_SENSITIVITY = 0.5  # market haircut per unit of collateral dumped
FIRESALE_CAP = 0.5  # max extra haircut from fire-sales


@dataclass(frozen=True)
class CascadeRun:
    seed: str
    rounds: int
    defaulted: int  # total entities defaulted at convergence
    second_order: int  # beyond the seed's own group
    total_loss: Decimal
    firesale_haircut: Decimal


def cascade_multiround(
    spec: DatasetSpec,
    head: str,
    *,
    buffer_fraction: float = BUFFER_FRACTION,
    firesale_sensitivity: float = FIRESALE_SENSITIVITY,
    max_rounds: int = 12,
) -> CascadeRun:
    """Iterate the default cascade to a fixed point, with guarantee + fire-sale contagion."""
    defaulted = set(group_members(spec, head))
    initial = set(defaulted)
    active = _active_loans(spec)
    total_collateral = sum((c.collateral_value or 0) for c in spec.collateral) or 1
    rounds = 0
    firesale = 0.0
    while rounds < max_rounds:
        rounds += 1
        dumped = sum(
            (c.collateral_value or 0) for c in spec.collateral if c.pledged_by_id in defaulted
        )
        firesale = min(FIRESALE_CAP, firesale_sensitivity * dumped / total_collateral)
        # guarantee obligations imposed on solvent guarantors by defaulted borrowers
        obligations: dict[str, Decimal] = {}
        for g in spec.guarantees:
            borrower = _borrower_of(spec, g.guaranteed_loan_id)
            if borrower in defaulted and g.guarantor_id not in defaulted:
                obligations[g.guarantor_id] = obligations.get(g.guarantor_id, Decimal(0)) + g.amount
        new: set[str] = set()
        for entity, obligation in obligations.items():
            buffer = Decimal(str(buffer_fraction * (1 - firesale))) * net_exposure(spec, entity)
            if obligation > buffer:  # the guarantor is overwhelmed -> it defaults
                new |= group_members(spec, entity)
        if new <= defaulted:
            break
        defaulted |= new

    lgd_eff = min(1.0, float(LGD) + firesale)  # recoveries impaired by the fire-sale
    loss = sum(
        (
            Decimal(str(lgd_eff)) * ln.principal
            for ln in active
            if ln.borrower_id in defaulted and not _solvent_guarantor(spec, ln.loan_id, defaulted)
        ),
        Decimal(0),
    )
    return CascadeRun(
        seed=head,
        rounds=rounds,
        defaulted=len(defaulted),
        second_order=len(defaulted) - len(initial),
        total_loss=loss,
        firesale_haircut=Decimal(str(round(firesale, 3))),
    )


def systemic_ranking_multiround(spec: DatasetSpec) -> list[CascadeRun]:
    """Multi-round cascade for every group, sorted by total loss desc."""
    rows = [cascade_multiround(spec, head) for head in top_level_names(spec)]
    return sorted(rows, key=lambda c: c.total_loss, reverse=True)
