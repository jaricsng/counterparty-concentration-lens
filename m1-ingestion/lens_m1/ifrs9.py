"""Simplified IFRS-9 expected credit loss (ECL) staging — deterministic, labelled.

DELIBERATELY SIMPLIFIED and clearly labelled — **not** a full IFRS-9 model:
  * Staging is a simple **rating rule** — no quantitative SICR test, no 30-days-past-due
    backstop, no forward-looking macro scenarios, no low-credit-risk exemption.
  * Lifetime ECL uses a **constant-hazard** PD term structure derived from the 1y PD
    over the loan tenor — not a calibrated lifetime PD curve.

    Stage 1 (performing)        -> 12-month ECL = PD₁ᵧ · LGD · EAD
    Stage 2 (SICR, sub-IG)      -> lifetime ECL = Σ marginalPD(t) · LGD · EAD · DF(t)
    Stage 3 (credit-impaired)   -> LGD · EAD            (default assumed)

Reuses the rating PD (lens_m1.credit_risk) and the loan tenor (maturity_years).
See docs/ccr-coverage.md for what remains out of scope (full IFRS-9 / IRB / macro).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from . import credit_risk, metrics
from .spec import DatasetSpec

DISCOUNT_RATE = 0.03
LGD = float(credit_risk.LGD)

# Staging by rating grade (the simplified SICR proxy).
STAGE3_GRADES = {"CCC"}  # credit-impaired
STAGE2_GRADES = {"BB", "B"}  # significant increase in credit risk (sub-investment-grade)


def stage_for(rating: str | None) -> int:
    """IFRS-9 stage from rating: 3 (CCC), 2 (sub-IG / unrated), else 1 (investment grade)."""
    if rating in STAGE3_GRADES:
        return 3
    if not rating or rating in STAGE2_GRADES:
        return 2
    return 1


def lifetime_ecl(
    ead: float, maturity_years: int, pd_1yr: float, *, rate: float = DISCOUNT_RATE
) -> float:
    """Lifetime ECL = Σ marginalPD(t) · LGD · EAD · DF(t) over the tenor (constant hazard)."""
    if ead <= 0 or pd_1yr <= 0:
        return 0.0
    hazard = -math.log(1.0 - pd_1yr) if pd_1yr < 1.0 else 5.0
    horizon = max(1, maturity_years)
    total = 0.0
    prev_survival = 1.0
    for year in range(1, horizon + 1):
        survival = math.exp(-hazard * year)
        marginal_pd = prev_survival - survival
        total += marginal_pd * LGD * ead * math.exp(-rate * year)
        prev_survival = survival
    return total


@dataclass(frozen=True)
class CounterpartyECL:
    entity: str
    rating: str
    stage: int
    ead: Decimal
    ecl_12m: Decimal
    ecl_lifetime: Decimal
    ecl_recognised: Decimal  # 12m for stage 1, else lifetime (stage 3 = LGD·EAD)

    @property
    def coverage(self) -> Decimal:
        return self.ecl_recognised / self.ead if self.ead else Decimal(0)


def _representative_tenor(spec: DatasetSpec, entity_id: str) -> int:
    tenors = [
        ln.maturity_years for ln in metrics._active_loans(spec) if ln.borrower_id == entity_id
    ]
    return max(tenors, default=3)


def counterparty_ecl(spec: DatasetSpec, entity_id: str) -> CounterpartyECL:
    """Stage + 12-month / lifetime / recognised ECL for one counterparty (net EAD)."""
    ead = float(metrics.net_exposure(spec, entity_id))
    rating = spec.entity(entity_id).rating
    stage = stage_for(rating)
    pd_1yr = float(credit_risk.pd_for(rating))
    ecl_12m = pd_1yr * LGD * ead
    ecl_life = lifetime_ecl(ead, _representative_tenor(spec, entity_id), pd_1yr)
    if stage == 1:
        recognised = ecl_12m
    elif stage == 3:
        recognised = LGD * ead  # default assumed
    else:
        recognised = ecl_life
    return CounterpartyECL(
        entity=entity_id,
        rating=rating or "unrated",
        stage=stage,
        ead=Decimal(str(round(ead, 2))),
        ecl_12m=Decimal(str(round(ecl_12m, 2))),
        ecl_lifetime=Decimal(str(round(ecl_life, 2))),
        ecl_recognised=Decimal(str(round(recognised, 2))),
    )


def portfolio_ecl(spec: DatasetSpec) -> list[CounterpartyECL]:
    """Per-counterparty ECL for every active borrower, sorted by recognised ECL desc."""
    borrowers = sorted({ln.borrower_id for ln in metrics._active_loans(spec)})
    rows = [counterparty_ecl(spec, b) for b in borrowers]
    return sorted(rows, key=lambda r: r.ecl_recognised, reverse=True)


@dataclass(frozen=True)
class StagingSummary:
    stage: int
    count: int
    ead: Decimal
    ecl: Decimal


def staging_summary(spec: DatasetSpec) -> list[StagingSummary]:
    """Counterparty count, EAD and recognised ECL per IFRS-9 stage."""
    rows = portfolio_ecl(spec)
    out: list[StagingSummary] = []
    for stage in (1, 2, 3):
        members = [r for r in rows if r.stage == stage]
        out.append(
            StagingSummary(
                stage=stage,
                count=len(members),
                ead=sum((r.ead for r in members), Decimal(0)),
                ecl=sum((r.ecl_recognised for r in members), Decimal(0)),
            )
        )
    return out


def total_ecl(spec: DatasetSpec) -> Decimal:
    return sum((r.ecl_recognised for r in portfolio_ecl(spec)), Decimal(0))
