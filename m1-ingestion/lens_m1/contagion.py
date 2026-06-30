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
from .metrics import _active_loans, _borrower_of, group_members, top_level_names
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
