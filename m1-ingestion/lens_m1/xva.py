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


# --------------------------------------------------------------------------- #
#  Full xVA breakdown (CVA · DVA · FVA · MVA · KVA) — analytical, illustrative.
#  Each is a deterministic integral over the same EE/PFE profile + a flat
#  parameter; NOT simulated. DVA ≈ 0 for a pure loan book (one-directional
#  exposure) — we model a symmetric band purely to show the bilateral framework.
# --------------------------------------------------------------------------- #

FUNDING_SPREAD = 0.01  # funding cost over the risk-free curve (100 bps)
COST_OF_CAPITAL = 0.10  # hurdle rate for KVA
OWN_RATING = "AAA"  # the lending bank's own rating (for DVA)


def _df(t: float, rate: float = DISCOUNT_RATE) -> float:
    return math.exp(-rate * t)


def fva(ead: float, maturity_years: int, vol: float = SUPERVISORY_VOL) -> float:
    """Funding VA — funding the uncollateralised expected exposure at a funding spread."""
    return sum(p.ee * FUNDING_SPREAD * _df(p.t) for p in exposure_profile(ead, maturity_years, vol))


def mva(ead: float, maturity_years: int, vol: float = SUPERVISORY_VOL) -> float:
    """Margin VA — funding initial margin (proxied by the PFE add-on) at a funding spread."""
    prof = exposure_profile(ead, maturity_years, vol)
    return sum(2.0 * (p.pfe - p.ee) * FUNDING_SPREAD * _df(p.t) for p in prof)


def kva(ead: float, maturity_years: int, rating: str | None, vol: float = SUPERVISORY_VOL) -> float:
    """Capital VA — cost of holding capital (8%·RW·EE) over the life at the hurdle rate."""
    rw = float(credit_risk.rw_for(rating))
    prof = exposure_profile(ead, maturity_years, vol)
    return sum(0.08 * rw * p.ee * COST_OF_CAPITAL * _df(p.t) for p in prof)


def dva(ead: float, maturity_years: int, vol: float = SUPERVISORY_VOL) -> float:
    """Debt VA — the mirror of CVA from our OWN default (≈0 for a loan book)."""
    own_pd = float(credit_risk.pd_for(OWN_RATING))
    if ead <= 0 or own_pd <= 0:
        return 0.0
    hazard = -math.log(1.0 - own_pd)
    prof = exposure_profile(ead, maturity_years, vol)
    total = 0.0
    prev_survival = 1.0
    for p in prof:
        if p.t == 0.0:
            continue
        survival = math.exp(-hazard * p.t)
        neg_ee = 0.5 * 2.0 * (p.pfe - p.ee)  # the negative side of the diffusion band
        total += LGD * neg_ee * (prev_survival - survival) * _df(p.t)
        prev_survival = survival
    return total


@dataclass(frozen=True)
class XvaBreakdown:
    entity: str
    rating: str
    cva: Decimal
    dva: Decimal
    fva: Decimal
    mva: Decimal
    kva: Decimal

    @property
    def total_xva(self) -> Decimal:
        """Total valuation adjustment: CVA − DVA + FVA + MVA + KVA."""
        return self.cva - self.dva + self.fva + self.mva + self.kva


def counterparty_xva_breakdown(spec: DatasetSpec, entity_id: str) -> XvaBreakdown:
    ead = float(metrics.net_exposure(spec, entity_id))
    tenor = _representative_tenor(spec, entity_id)
    rating = spec.entity(entity_id).rating
    return XvaBreakdown(
        entity=entity_id,
        rating=rating or "unrated",
        cva=Decimal(str(round(cva(ead, tenor, float(credit_risk.pd_for(rating))), 2))),
        dva=Decimal(str(round(dva(ead, tenor), 2))),
        fva=Decimal(str(round(fva(ead, tenor), 2))),
        mva=Decimal(str(round(mva(ead, tenor), 2))),
        kva=Decimal(str(round(kva(ead, tenor, rating), 2))),
    )


def portfolio_xva_breakdown(spec: DatasetSpec) -> list[XvaBreakdown]:
    """Full xVA breakdown per active borrower, sorted by total xVA desc."""
    borrowers = sorted({ln.borrower_id for ln in metrics._active_loans(spec)})
    rows = [counterparty_xva_breakdown(spec, b) for b in borrowers]
    return sorted(rows, key=lambda r: r.total_xva, reverse=True)
