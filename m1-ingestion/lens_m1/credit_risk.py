"""Simplified, deterministic credit-risk layer: EAD, Expected Loss, capital.

DELIBERATELY SIMPLIFIED — structurally honest, clearly labelled, NOT a production
model and NOT claiming regulatory accuracy:

  * EAD  = current **net (post-collateral) exposure** (the merged netting feature).
           Point-in-time; **no PFE add-on** (no Monte-Carlo — the synthetic data is
           a single snapshot, not a simulated path).
  * PD   = mapped from the **credit rating** (the merged rating feature) via an
           illustrative table — synthetic, not a rating agency's published PDs.
  * LGD  = flat 45% (Basel foundation, unsecured) on the post-collateral EAD.
  * EL   = PD x LGD x EAD  (~ a 12-month ECL point estimate; **NOT** full IFRS-9
           staging / lifetime ECL / macro overlays).
  * RWA  = standardised-approach risk weight (from rating) x EAD; capital = 8% x RWA.

This layer reuses the two merged features (net exposure -> EAD; rating -> PD/RW) and
turns concentration into a loss/capital view. See docs/concentration-metrics.md §10
for what remains deliberately out of scope (Monte-Carlo PFE/CVA, full IFRS-9, IRB).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .metrics import _active_loans, net_exposure
from .spec import DatasetSpec

# Illustrative 1-year PD by rating grade (SYNTHETIC — not a rating agency's data).
PD_BY_RATING: dict[str, Decimal] = {
    "AAA": Decimal("0.0001"),
    "AA": Decimal("0.0002"),
    "A": Decimal("0.0005"),
    "BBB": Decimal("0.0025"),
    "BB": Decimal("0.01"),
    "B": Decimal("0.05"),
    "CCC": Decimal("0.20"),
}

# Standardised-approach risk weight by rating (illustrative corporate buckets).
RW_BY_RATING: dict[str, Decimal] = {
    "AAA": Decimal("0.20"),
    "AA": Decimal("0.20"),
    "A": Decimal("0.50"),
    "BBB": Decimal("1.00"),
    "BB": Decimal("1.00"),
    "B": Decimal("1.50"),
    "CCC": Decimal("1.50"),
}

LGD = Decimal("0.45")  # Basel foundation, unsecured
CAPITAL_RATIO = Decimal("0.08")  # 8% minimum capital
UNRATED_PD = Decimal("0.01")  # unrated treated as BB-equivalent (conservative)
UNRATED_RW = Decimal("1.00")


def pd_for(rating: str | None) -> Decimal:
    """1-year probability of default for a rating grade (unrated -> BB-equivalent)."""
    return PD_BY_RATING.get(rating or "", UNRATED_PD)


def rw_for(rating: str | None) -> Decimal:
    """Standardised-approach risk weight for a rating grade (unrated -> 100%)."""
    return RW_BY_RATING.get(rating or "", UNRATED_RW)


def expected_loss(ead: Decimal, rating: str | None) -> Decimal:
    """EL = PD x LGD x EAD."""
    return pd_for(rating) * LGD * ead


@dataclass(frozen=True)
class CreditRisk:
    entity: str
    rating: str
    ead: Decimal
    pd: Decimal
    lgd: Decimal
    el: Decimal  # expected loss
    rwa: Decimal
    capital: Decimal  # 8% x RWA


def credit_risk(spec: DatasetSpec, entity_id: str) -> CreditRisk:
    """Per-counterparty EAD / PD / EL / RWA / capital (point-in-time, simplified)."""
    ead = net_exposure(spec, entity_id)  # post-collateral EAD
    rating = spec.entity(entity_id).rating
    rwa = rw_for(rating) * ead
    return CreditRisk(
        entity=entity_id,
        rating=rating or "unrated",
        ead=ead,
        pd=pd_for(rating),
        lgd=LGD,
        el=expected_loss(ead, rating),
        rwa=rwa,
        capital=CAPITAL_RATIO * rwa,
    )


def portfolio_credit_risk(spec: DatasetSpec) -> list[CreditRisk]:
    """Credit-risk rows for every active borrower, sorted by expected loss desc."""
    borrowers = sorted({ln.borrower_id for ln in _active_loans(spec)})
    rows = [credit_risk(spec, b) for b in borrowers]
    return sorted(rows, key=lambda r: r.el, reverse=True)


@dataclass(frozen=True)
class PortfolioSummary:
    total_ead: Decimal
    total_el: Decimal
    total_rwa: Decimal
    total_capital: Decimal
    capital_as_pct_of_eligible: Decimal  # total capital / the bank's eligible capital


def portfolio_summary(spec: DatasetSpec) -> PortfolioSummary:
    """Book-level EAD / EL / RWA / capital and capital as a share of eligible capital."""
    rows = portfolio_credit_risk(spec)
    total_rwa = sum((r.rwa for r in rows), Decimal(0))
    total_capital = CAPITAL_RATIO * total_rwa
    eligible = next((e.eligible_capital for e in spec.entities if e.eligible_capital), 0) or 1
    return PortfolioSummary(
        total_ead=sum((r.ead for r in rows), Decimal(0)),
        total_el=sum((r.el for r in rows), Decimal(0)),
        total_rwa=total_rwa,
        total_capital=total_capital,
        capital_as_pct_of_eligible=total_capital / Decimal(eligible),
    )
