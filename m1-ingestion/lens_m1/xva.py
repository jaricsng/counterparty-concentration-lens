"""Forward-looking exposure (PFE / EE) and CVA — analytical & deterministic.

DELIBERATELY SIMPLIFIED, clearly labelled, **not** a production xVA engine and
**not** Monte-Carlo. Instead of simulating exposure paths we build an ANALYTICAL
profile (an amortising base exposure plus a √t diffusion add-on) and integrate the
standard unilateral-CVA formula over it. The synthetic data is a single snapshot,
so the profile *shape* is illustrative — it shows how the framework treats an
uncertain future exposure, not a calibrated market simulation.

    outstanding(t) = EAD · (1 − t/T)              # linear amortisation to maturity
    addon(t)       = EAD · vol · √t               # diffusion band (grows with √t)
    EE(t)          = outstanding(t) + 0.5·addon(t) # expected exposure
    PFE(t)         = outstanding(t) + addon(t)     # potential future exposure (band)
    CVA = LGD · Σ EE(tᵢ) · marginalPD(tᵢ) · DF(tᵢ) # hazard from the rating's 1y PD

See docs/concentration-metrics.md §10 and docs/ccr-coverage.md for what stays out
of scope (Monte-Carlo PFE/EE, full xVA: FVA/MVA/KVA, derivative MtM).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

from . import credit_risk, metrics
from .spec import DatasetSpec

SUPERVISORY_VOL = 0.15  # illustrative annual exposure volatility
DISCOUNT_RATE = 0.03  # flat discount rate for CVA
LGD = float(credit_risk.LGD)


@dataclass(frozen=True)
class ProfilePoint:
    t: float
    ee: float
    pfe: float


def exposure_profile(
    ead: float, maturity_years: int, vol: float = SUPERVISORY_VOL
) -> list[ProfilePoint]:
    """Analytical EE/PFE profile over yearly buckets 0..T (illustrative, not simulated)."""
    horizon = max(1, maturity_years)
    points: list[ProfilePoint] = []
    for i in range(horizon + 1):
        t = float(i)
        outstanding = ead * (1.0 - t / horizon)
        addon = ead * vol * math.sqrt(t)
        points.append(ProfilePoint(t, outstanding + 0.5 * addon, outstanding + addon))
    return points


def cva(
    ead: float,
    maturity_years: int,
    pd_1yr: float,
    *,
    lgd: float = LGD,
    rate: float = DISCOUNT_RATE,
    vol: float = SUPERVISORY_VOL,
) -> float:
    """Unilateral CVA = LGD · Σ EE(t)·marginalPD(t)·DF(t), hazard from the 1y PD."""
    profile = exposure_profile(ead, maturity_years, vol)
    hazard = -math.log(1.0 - pd_1yr) if 0.0 < pd_1yr < 1.0 else (5.0 if pd_1yr >= 1.0 else 0.0)
    total = 0.0
    prev_survival = 1.0
    for point in profile:
        if point.t == 0.0:
            continue
        survival = math.exp(-hazard * point.t)
        marginal_pd = prev_survival - survival
        discount = math.exp(-rate * point.t)
        total += lgd * point.ee * marginal_pd * discount
        prev_survival = survival
    return total


@dataclass(frozen=True)
class CounterpartyXVA:
    entity: str
    rating: str
    ead: Decimal
    maturity: int
    peak_pfe: Decimal  # max potential future exposure over the horizon
    epe: Decimal  # expected positive exposure (time-average EE)
    cva: Decimal


def _representative_tenor(spec: DatasetSpec, entity_id: str) -> int:
    tenors = [
        ln.maturity_years for ln in metrics._active_loans(spec) if ln.borrower_id == entity_id
    ]
    return max(tenors, default=3)


def counterparty_xva(spec: DatasetSpec, entity_id: str) -> CounterpartyXVA:
    """PFE / EE / CVA for one counterparty on its net (post-collateral) EAD."""
    ead = float(metrics.net_exposure(spec, entity_id))
    tenor = _representative_tenor(spec, entity_id)
    rating = spec.entity(entity_id).rating
    profile = exposure_profile(ead, tenor)
    return CounterpartyXVA(
        entity=entity_id,
        rating=rating or "unrated",
        ead=Decimal(str(round(ead, 2))),
        maturity=tenor,
        peak_pfe=Decimal(str(round(max((p.pfe for p in profile), default=0.0), 2))),
        epe=Decimal(str(round(sum(p.ee for p in profile) / len(profile), 2))),
        cva=Decimal(str(round(cva(ead, tenor, float(credit_risk.pd_for(rating))), 2))),
    )


def portfolio_xva(spec: DatasetSpec) -> list[CounterpartyXVA]:
    """Per-counterparty PFE/EE/CVA for every active borrower, sorted by CVA desc."""
    borrowers = sorted({ln.borrower_id for ln in metrics._active_loans(spec)})
    rows = [counterparty_xva(spec, b) for b in borrowers]
    return sorted(rows, key=lambda r: r.cva, reverse=True)


def total_cva(spec: DatasetSpec) -> Decimal:
    return sum((r.cva for r in portfolio_xva(spec)), Decimal(0))
